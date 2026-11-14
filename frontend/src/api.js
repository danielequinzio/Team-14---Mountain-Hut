const API_BASE_URL = "http://localhost:8000";

// Change this to false when you want to use FastAPI.
const USE_MOCK_DATA = false;

// ----------------------------------
// MOCK DATA
// ----------------------------------

function getLocalDate(daysFromToday) {
  const date = new Date();
  date.setDate(date.getDate() + daysFromToday);

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

const mockAvailability = {
  [getLocalDate(1)]: [
    {
      id: 1,
      start: "11:00:00",
      end: "12:00:00",
      availableSeats: 5,
    },
    {
      id: 2,
      start: "12:00:00",
      end: "13:00:00",
      availableSeats: 8,
    },
    {
      id: 3,
      start: "19:00:00",
      end: "20:00:00",
      availableSeats: 4,
    },
  ],

  [getLocalDate(3)]: [
    {
      id: 4,
      start: "10:00:00",
      end: "11:00:00",
      availableSeats: 2,
    },
    {
      id: 5,
      start: "13:00:00",
      end: "14:00:00",
      availableSeats: 10,
    },
  ],

  [getLocalDate(5)]: [
    {
      id: 6,
      start: "11:00:00",
      end: "12:00:00",
      availableSeats: 6,
    },
    {
      id: 7,
      start: "17:00:00",
      end: "18:00:00",
      availableSeats: 3,
    },
  ],

  [getLocalDate(8)]: [
    {
      id: 8,
      start: "14:00:00",
      end: "15:00:00",
      availableSeats: 7,
    },
  ],
};

// ----------------------------------
// GET AVAILABILITY
// ----------------------------------

// POST /slot/{id} sends the slot start/end in UTC. The hut works in Rome time, so
// convert to a Rome-time "YYYY-MM-DDTHH:MM:SS" string: every page that shows a
// time just cuts out HH:MM, and then matches the date, the email and the staff page.
const HUT_TIMEZONE = "Europe/Rome";

function toHutLocalIso(utcDateTime) {
  if (!utcDateTime) return utcDateTime;
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(utcDateTime);
  const moment = new Date(hasZone ? utcDateTime : `${utcDateTime}Z`);
  if (Number.isNaN(moment.getTime())) return utcDateTime;
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-GB", {
      timeZone: HUT_TIMEZONE,
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(moment)
      .map((part) => [part.type, part.value])
  );
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}:${parts.second}`;
}

export async function getAvailability() {
  // Use mock data
  if (USE_MOCK_DATA) {
    console.log("Using MOCK availability data");

    // Mirror the real API: each slot carries a plain "HH:MM:SS" time for booking
    return Object.fromEntries(
      Object.entries(mockAvailability).map(([date, slots]) => [
        date,
        slots.map((slot) => ({ ...slot, time: slot.start })),
      ])
    );
  }

  // Use real FastAPI backend
  const response = await fetch(`${API_BASE_URL}/slot`, {
    method: "GET",
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error("Could not fetch available slots.");
  }

  const slots = await response.json();

  const detailedSlots = await Promise.all(
    slots.map(async (slot) => {
      const detailResponse = await fetch(
        `${API_BASE_URL}/slot/${slot.id}`,
        {
          method: "GET",
          credentials: "include",
        }
      );

      if (!detailResponse.ok) {
        throw new Error(`Could not fetch slot ${slot.id}.`);
      }

      const details = await detailResponse.json();

      return {
        id: slot.id,
        date: slot.date,
        // Hut-local "HH:MM:SS" start time: POST /booking expects this, not a datetime
        time: slot.time,
        start: toHutLocalIso(details.start_time),
        end: toHutLocalIso(details.end_time),
        availableSeats: slot.available_seats,
      };
    })
  );

  const availability = {};

  detailedSlots.forEach((slot) => {
    if (!availability[slot.date]) {
      availability[slot.date] = [];
    }

    availability[slot.date].push(slot);
  });

  return availability;
}

// ----------------------------------
// CREATE BOOKING
// ----------------------------------

export async function createBooking({
  date,
  time,
  partySize,
}) {
  // Simulate a successful booking
  if (USE_MOCK_DATA)  {
    console.log("Creating MOCK booking");

    const selectedSlots = mockAvailability[date] || [];

    const slot = selectedSlots.find(
      (item) => item.start === time
    );

    if (!slot) {
      throw new Error("This time slot is no longer available.");
    }

    if (partySize > slot.availableSeats) {
      throw new Error("Not enough seats available.");
    }

    return {
      id: Math.floor(Math.random() * 10000),
      date,
      time,
      party_size: partySize,
      tables: [
        {
          number: 5,
        },
      ],
      status: "confirmed",
    };
  }

  // Send booking to FastAPI
  const response = await fetch(`${API_BASE_URL}/booking`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      date,
      time,
      party_size: partySize,
    }),
  });

  const data = await response.json();

  if (!response.ok) {
    // FastAPI validation errors (422) return detail as an array of objects
    const message = Array.isArray(data?.detail)
      ? data.detail.map((item) => item.msg).join(", ")
      : data?.detail;

    throw new Error(message || "Could not create reservation.");
  }

  return data;
}

// Employee time-slot API. Kept separate from the hiker booking API.
// Set USE_MOCK_SLOT_DATA=false when the FastAPI server and employee session are ready.
export const USE_MOCK_SLOT_DATA = false;

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
// the backend sends UTC: cut the date and times out of the Rome-time version
const slotDate = (slot) => String(toHutLocalIso(slot.start_time) ?? "").slice(0, 10);
const slotStart = (slot) => String(toHutLocalIso(slot.start_time) ?? "").slice(11, 16);
const slotEnd = (slot) => String(toHutLocalIso(slot.end_time) ?? "").slice(11, 16);

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
  // POST /slots rejects datetimes without a timezone ("must have timezone
  // information"). The employee types the hut's wall-clock time (Rome), so work
  // out which UTC instant that is and send it as a UTC timestamp.
  const [year, month, day] = date.split("-").map(Number);
  const [hour, minute] = time.split(":").map(Number);
  const guess = Date.UTC(year, month - 1, day, hour, minute);
  const wall = Object.fromEntries(
    new Intl.DateTimeFormat("en-GB", {
      timeZone: "Europe/Rome",
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hourCycle: "h23",
    })
      .formatToParts(new Date(guess))
      .map((part) => [part.type, Number(part.value)])
  );
  const wallAsUtc = Date.UTC(wall.year, wall.month - 1, wall.day, wall.hour, wall.minute);
  const offset = wallAsUtc - guess; // Rome is ahead of UTC by this much at that moment
  return new Date(guess - offset).toISOString();
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

// Every physical table of the hut (GET /tables), sorted by table number.
export async function getHutTables() {
  const result = USE_MOCK_SLOT_DATA ? clone(mockTables) : await request("/tables");
  return (Array.isArray(result) ? result : [])
    .map((table) => ({
      id: table.id,
      number: Number(table.number),
      size: Number(table.capacity),
      capacity: Number(table.capacity),
      location: table.location ?? "",
    }))
    .sort((a, b) => a.number - b.number);
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
      assigned = clone(tables || []).map((table) => {
        let physical = mockTables.find((t) => t.number === table.number);
        if (!physical) {
          physical = {
            id: Math.max(0, ...mockTables.map((t) => t.id)) + 1,
            number: table.number,
            capacity: table.capacity ?? table.size,
            location: table.location,
          };
          mockTables.push(physical);
        }
        return clone(physical);
      });
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

// ----------------------------------
// MY BOOKINGS
// ----------------------------------

export function getMyBookings() {
  return request("/booking");
}