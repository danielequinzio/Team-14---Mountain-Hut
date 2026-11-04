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

In the `.env` file change:

```env
VITE_USE_MOCK_DATA=false
VITE_API_BASE_URL=http://localhost:8000
```

## Main behavior

- Dates without available slots cannot be clicked.
- Clicking an available date displays all its time slots.
- Every time slot shows start/end time and available seats.
- Party size can never exceed the selected slot's capacity.
- Changing time slots automatically keeps the party size valid.
- The UI can be developed and tested entirely without the backend.
