// Employee time-slot API. Kept separate from the hiker booking API.
// Set USE_MOCK_SLOT_DATA=false when the FastAPI server and employee session are ready.
export const USE_MOCK_SLOT_DATA = false;
const API_BASE_URL = "http://localhost:8000";

const mockSlots = [
  { id: 201, start_time: "2026-11-03T11:00:00+01:00", end_time: "2026-11-03T12:30:00+01:00",
    tables: [{ id: 1, number: 1, capacity: 4, location: "Main hall" }, { id: 2, number: 2, capacity: 2, location: "Window" }] },
  { id: 202, start_time: "2026-11-03T18:00:00+01:00", end_time: "2026-11-03T19:30:00+01:00",
    tables: [{ id: 1, number: 1, capacity: 4, location: "Main hall" }, { id: 3, number: 3, capacity: 6, location: "Terrace" }] },
  { id: 203, start_time: "2026-11-05T12:00:00+01:00", end_time: "2026-11-05T13:30:00+01:00",
    tables: [{ id: 4, number: 4, capacity: 2, location: "Main hall" }, { id: 5, number: 5, capacity: 8, location: "Window" }] },
];
let mockNextId = 204;
let mockTables = [
  { id: 1, number: 1, capacity: 4, location: "Main hall" },
  { id: 2, number: 2, capacity: 2, location: "Window" },
  { id: 3, number: 3, capacity: 6, location: "Terrace" },
  { id: 4, number: 4, capacity: 2, location: "Main hall" },
  { id: 5, number: 5, capacity: 8, location: "Window" },
];

const clone = (value) => JSON.parse(JSON.stringify(value));
const slotDate = (slot) => String(slot.start_time ?? "").slice(0, 10);
const slotStart = (slot) => String(slot.start_time ?? "").slice(11, 16);
const slotEnd = (slot) => String(slot.end_time ?? "").slice(11, 16);

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  const body = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail;
    throw new Error(typeof detail === "string" ? detail : `Request failed (${response.status}).`);
  }
  return body;
}

function localDateTime(date, time) {
  // FastAPI receives ISO datetime values. The backend interprets naive datetimes
  // in Europe/Rome for its availability calculations.
  return `${date}T${time}:00`;
}

export async function getEmployeeSlots(date) {
  if (USE_MOCK_SLOT_DATA) {
    return clone(mockSlots.filter((slot) => slotDate(slot) === date).map((slot) => ({
      ...slot, date: slotDate(slot), start: slotStart(slot), end: slotEnd(slot),
    })));
  }
  const query = date ? `?date=${encodeURIComponent(date)}` : "";
  const result = await request(`/slots${query}`);
  return (Array.isArray(result) ? result : []).map((slot) => ({
    ...slot,
    date: slotDate(slot),
    start: slotStart(slot),
    end: slotEnd(slot),
  }));
}

export async function getTablesForSlot(slotId) {
  if (USE_MOCK_SLOT_DATA) {
    const slot = mockSlots.find((item) => String(item.id) === String(slotId));
    if (!slot) throw new Error("The selected time slot was not found.");
    return clone(slot.tables);
  }

  // SlotDetail exposes table_id, seats_free and seats_booked.
  // GET /tables supplies the physical table number, capacity and location.
  const [detail, allTables] = await Promise.all([
    request(`/slots/${slotId}`),
    request("/tables"),
  ]);
  const byId = new Map((allTables || []).map((table) => [table.id, table]));
  return (detail?.tables || []).map((assignment) => {
    const physical = byId.get(assignment.table_id);
    if (!physical) throw new Error(`Could not find physical table ${assignment.table_id}.`);
    return {
      id: physical.id,
      number: physical.number,
      size: physical.capacity,
      capacity: physical.capacity,
      location: physical.location,
    };
  });
}

export async function createEmployeeSlot({ date, start, end, tables, sourceSlotId = null }) {
  if (USE_MOCK_SLOT_DATA) {
    let assigned;
    if (sourceSlotId) {
      const source = mockSlots.find((slot) => String(slot.id) === String(sourceSlotId));
      if (!source) throw new Error("The source time slot no longer exists.");
      assigned = clone(source.tables);
    } else {
      assigned = clone(tables || []).map((table, index) => ({
        id: table.id ?? (mockTables.find((t) => t.number === table.number)?.id ?? 1000 + index),
        number: table.number,
        capacity: table.capacity ?? table.size,
        location: table.location,
      }));
    }
    const created = {
      id: mockNextId++,
      start_time: localDateTime(date, start),
      end_time: localDateTime(date, end),
      tables: assigned,
    };
    mockSlots.push(created);
    return clone(created);
  }

  // 1) Create the slot. SlotCreate expects start_time and end_time.
  const createdSlot = await request("/slots", {
    method: "POST",
    body: JSON.stringify({
      start_time: localDateTime(date, start),
      end_time: localDateTime(date, end),
    }),
  });
  const targetId = createdSlot?.id;
  if (!targetId) throw new Error("The backend created the slot but did not return its ID.");

  // 2) If copying, the backend reuses the source slot's existing table IDs.
  if (sourceSlotId) {
    await request(`/slots/${sourceSlotId}/copy`, {
      method: "POST",
      body: JSON.stringify({ target_slot_id: targetId }),
    });
    return createdSlot;
  }

  // 3) Otherwise create/reuse physical tables, then assign their IDs.
  const existingTables = await request("/tables");
  const tableByNumber = new Map((existingTables || []).map((table) => [Number(table.number), table]));
  const tableIds = [];

  for (const draft of (tables || [])) {
    let physical = tableByNumber.get(Number(draft.number));
    if (physical) {
      // A table number is globally unique in this backend. Do not silently
      // overwrite its capacity/location; require the employee to reuse it.
      if (Number(physical.capacity) !== Number(draft.capacity ?? draft.size)) {
        throw new Error(`Table ${draft.number} already exists with capacity ${physical.capacity}.`);
      }
    } else {
      physical = await request("/tables", {
        method: "POST",
        body: JSON.stringify({
          number: Number(draft.number),
          capacity: Number(draft.capacity ?? draft.size),
          location: draft.location,
        }),
      });
      tableByNumber.set(Number(physical.number), physical);
    }
    tableIds.push(physical.id);
  }

  if (tableIds.length) {
    await request(`/slots/${targetId}/tables`, {
      method: "POST",
      body: JSON.stringify({ table_ids: tableIds }),
    });
  }
  return createdSlot;
}
