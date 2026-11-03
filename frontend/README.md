# Restaurant Booking - React + JavaScript

## Run without a backend

This project includes mock availability data by default.

```bash
npm install
npm run dev
```

Open the Vite URL in your browser.

The mock backend simulation intentionally includes dates with no availability,
so you can test disabled dates, time slots, seat limits, and party-size changes.

## Use the real backend

Create a `.env` file:

```env
VITE_USE_MOCK_DATA=false
VITE_API_BASE_URL=http://localhost:8080
```

The frontend then calls:

```http
GET /api/availability?from=YYYY-MM-DD&to=YYYY-MM-DD
```

Expected response:

```json
{
  "dates": [
    {
      "date": "2026-11-03",
      "slots": [
        {
          "start": "11:00",
          "end": "12:00",
          "availableSeats": 5
        },
        {
          "start": "12:30",
          "end": "13:30",
          "availableSeats": 2
        }
      ]
    },
    {
      "date": "2026-11-04",
      "slots": []
    }
  ]
}
```

If your backend returns a different JSON structure, only `src/api.js`
needs to be adapted.

## Main behavior

- Dates without available slots cannot be clicked.
- Clicking an available date displays all its time slots.
- Every time slot shows start/end time and available seats.
- Party size can never exceed the selected slot's capacity.
- Changing time slots automatically keeps the party size valid.
- The UI can be developed and tested entirely without the backend.
