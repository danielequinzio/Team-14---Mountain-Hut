// Dates, times and seat counts for the staff slot page.
//
// The backend sends slot times in UTC ("2026-11-05T11:00:00Z"). The hut works in
// Italian time, so everything shown on screen is converted to Europe/Rome, and
// the "day" of a slot is its day in Rome too (that is how GET /slots?date= works).

export const HUT_TIME_ZONE = "Europe/Rome";

const timeFormat = new Intl.DateTimeFormat("en-GB", {
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: HUT_TIME_ZONE,
});

// "en-CA" prints dates as YYYY-MM-DD
const dayFormat = new Intl.DateTimeFormat("en-CA", { timeZone: HUT_TIME_ZONE });

const longDayFormat = new Intl.DateTimeFormat("en-GB", {
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "UTC", // the input is already a plain calendar date
});

export function formatTime(iso) {
  return timeFormat.format(new Date(iso));
}

export function formatTimeRange(startIso, endIso) {
  return `${formatTime(startIso)} – ${formatTime(endIso)}`;
}

// "YYYY-MM-DD" of an instant, in the hut's time zone.
export function hutDay(iso) {
  return dayFormat.format(new Date(iso));
}

export function todayInHut() {
  return dayFormat.format(new Date());
}

// "2026-11-05" + 1 -> "2026-11-06" (plain calendar arithmetic, no time zones)
export function addDays(day, amount) {
  const [year, month, date] = day.split("-").map(Number);
  const moved = new Date(Date.UTC(year, month - 1, date + amount));
  return moved.toISOString().slice(0, 10);
}

export function formatLongDay(day) {
  const [year, month, date] = day.split("-").map(Number);
  return longDayFormat.format(new Date(Date.UTC(year, month - 1, date)));
}

export function isValidDay(day) {
  return /^\d{4}-\d{2}-\d{2}$/.test(day) && !Number.isNaN(Date.parse(day));
}

// Combines GET /slots/{id} with the table list (number and location of each table).
export function summariseSlot(detail, tablesById) {
  const tables = detail.tables
    .map((entry) => {
      const info = tablesById.get(entry.table_id);
      return {
        key: entry.id,
        number: info ? info.number : null,
        location: info ? info.location : "",
        booked: entry.seats_booked,
        free: entry.seats_free,
        capacity: entry.seats_booked + entry.seats_free,
      };
    })
    .sort((a, b) => (a.number ?? Infinity) - (b.number ?? Infinity));

  const booked = tables.reduce((sum, table) => sum + table.booked, 0);
  const free = tables.reduce((sum, table) => sum + table.free, 0);

  return {
    id: detail.id,
    start: detail.start_time,
    end: detail.end_time,
    tables,
    booked,
    free,
    capacity: booked + free,
  };
}

// How full a group of seats is, as a label and a colour name for the page.
export function occupancyStatus({ booked, free, capacity }) {
  if (capacity === 0) return { label: "No tables", tone: "muted" };
  if (free === 0) return { label: "Full", tone: "full" };
  if (free / capacity <= 0.25) return { label: "Almost full", tone: "warn" };
  if (booked === 0) return { label: "Empty", tone: "free" };
  return { label: "Available", tone: "free" };
}

export function percentBooked({ booked, capacity }) {
  return capacity === 0 ? 0 : Math.round((booked / capacity) * 100);
}
