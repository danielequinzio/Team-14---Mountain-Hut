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
        start: details.start_time,
        end: details.end_time,
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
