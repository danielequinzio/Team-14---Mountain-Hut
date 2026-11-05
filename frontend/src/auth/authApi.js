// Calls to the authentication endpoints of the FastAPI backend.
//
// The backend keeps the session in an HttpOnly cookie called "session", so every
// request is sent with credentials: "include". The cookie can't be read from
// JavaScript: to know who is logged in we ask GET /users/me.

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(message, status, fieldErrors = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status; // 0 = the server could not be reached
    this.fieldErrors = fieldErrors; // { fieldName: "message" } for 422 answers
  }
}

// Turns the body of an error answer into a message and per-field messages.
// The backend sends { detail: "text" } for 400/401/403/404/409 and
// { detail: [{ loc: [...], msg: "..." }] } for 422 (invalid fields).
export function describeError(data, status) {
  const detail = data && data.detail;

  if (typeof detail === "string") {
    return { message: detail, fieldErrors: {} };
  }

  if (Array.isArray(detail) && detail.length > 0) {
    const fieldErrors = {};
    for (const item of detail) {
      const field = Array.isArray(item.loc)
        ? String(item.loc[item.loc.length - 1])
        : "form";
      if (!fieldErrors[field]) fieldErrors[field] = item.msg;
    }
    return { message: "Some fields are not valid.", fieldErrors };
  }

  return { message: `Request failed (${status}).`, fieldErrors: {} };
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      credentials: "include",
      ...options,
    });
  } catch {
    throw new ApiError(
      "Cannot reach the server. Check that the backend is running.",
      0
    );
  }

  if (response.status === 204) return null;

  let data = null;
  try {
    data = await response.json();
  } catch {
    // an empty or non-JSON body: handled below
  }

  if (!response.ok) {
    const { message, fieldErrors } = describeError(data, response.status);
    throw new ApiError(message, response.status, fieldErrors);
  }

  return data;
}

function postJson(path, body) {
  return request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// POST /login -> { username, role }, and the server sets the session cookie.
export function login(email, password) {
  return postJson("/login", { email, password });
}

// POST /register -> { username, role }. It does NOT log the user in.
export function register(data) {
  return postJson("/register", data);
}

// POST /logout -> 204. Removes the session cookie.
export function logout() {
  return request("/logout", { method: "POST" });
}

// GET /users/me -> { username, role }, or null when nobody is logged in.
export async function getMe() {
  try {
    return await request("/users/me");
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}
