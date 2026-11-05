// Calls to the slot endpoints that only the employee and the warden may use.
//
//   GET /slots?date=YYYY-MM-DD   -> [{ id, start_time, end_time, created_by }]
//   GET /slots/{id}              -> { id, start_time, end_time, created_by,
//                                     tables: [{ id, table_id, seats_booked, seats_free }] }
//   GET /tables                  -> [{ id, number, capacity, location }]
//
// The session cookie is sent with every request (credentials: "include").

import { API_BASE_URL, ApiError, describeError } from "../auth/authApi";

async function get(path) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { credentials: "include" });
  } catch {
    throw new ApiError(
      "Cannot reach the server. Check that the backend is running.",
      0
    );
  }

  let data = null;
  try {
    data = await response.json();
  } catch {
    // an empty or non-JSON body: handled below
  }

  if (!response.ok) {
    const { message } = describeError(data, response.status);
    throw new ApiError(message, response.status);
  }

  return data;
}

// date and fromDate are "YYYY-MM-DD" strings in the hut's time zone.
export function listSlots({ date, fromDate } = {}) {
  const params = new URLSearchParams();
  if (date) params.set("date", date);
  if (fromDate) params.set("from_date", fromDate);
  const query = params.toString();
  return get(`/slots${query ? `?${query}` : ""}`);
}

export function getSlot(id) {
  return get(`/slots/${id}`);
}

export function listTables() {
  return get("/tables");
}
