const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_DATA !== "false";

/*
  Mock availability lets you develop the UI without a backend.

  To use your real backend later, put this in .env:
    VITE_USE_MOCK_DATA=false
    VITE_API_BASE_URL=http://localhost:8080
*/

function dateKey(year, month, day) {
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function buildMockAvailability(from, to) {
  const start = new Date(`${from}T00:00:00`);
  const end = new Date(`${to}T00:00:00`);
  const dates = [];

  for (
    const date = new Date(start);
    date <= end;
    date.setDate(date.getDate() + 1)
  ) {
    const day = date.getDay(); // 0 Sunday, 6 Saturday
    const key = dateKey(
      date.getFullYear(),
      date.getMonth() + 1,
      date.getDate()
    );

    // Some dates intentionally have no slots so you can test disabled dates.
    const isClosed =
      day === 1 ||
      (date.getDate() % 7 === 0) ||
      (day === 0 && date.getDate() % 2 === 0);

    if (isClosed) {
      dates.push({ date: key, slots: [] });
      continue;
    }

    const slots = [
      { start: "11:00", end: "12:00", availableSeats: 5 },
      { start: "12:30", end: "13:30", availableSeats: 8 },
      { start: "18:00", end: "19:00", availableSeats: 4 },
      { start: "19:30", end: "20:30", availableSeats: 2 }
    ];

    // Make a few dates have a different capacity to demonstrate
    // that party size follows the selected slot.
    if (date.getDate() % 5 === 0) {
      slots.splice(1, 1);
      slots[2].availableSeats = 6;
    }

    dates.push({ date: key, slots });
  }

  return dates;
}

export async function getAvailability(from, to) {
  if (USE_MOCK_DATA) {
    // Simulate a small network delay so loading states can be tested.
    await new Promise((resolve) => setTimeout(resolve, 250));
    return buildMockAvailability(from, to);
  }

  const url =
    `${API_BASE_URL}/api/availability?from=${encodeURIComponent(from)}` +
    `&to=${encodeURIComponent(to)}`;

  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Could not load availability (${response.status})`);
  }

  const data = await response.json();
  return data.dates ?? [];
}
