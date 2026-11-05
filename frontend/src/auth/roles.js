// Role names exactly as the backend returns them (UserPublic.role).
export const ROLES = {
  HIKER: "Hiker",
  EMPLOYEE: "Employee",
  WARDEN: "Warden",
};

// Employees and the warden share the same staff pages.
export const STAFF_ROLES = [ROLES.EMPLOYEE, ROLES.WARDEN];

export function isStaff(user) {
  return Boolean(user) && STAFF_ROLES.includes(user.role);
}

// Where a user lands right after logging in or registering: the home page, for
// every role. From there the header buttons lead to their own page (staff:
// "Manage slots", everyone else: "Book a table").
export function homePathFor() {
  return "/";
}

// The page to open right after a login: the page the user was trying to reach
// (when their role may see it), otherwise the home page.
export function resolveAfterLogin(user, from) {
  const isLocalPath =
    typeof from === "string" &&
    from.startsWith("/") &&
    !from.startsWith("//") &&
    from !== "/login" &&
    from !== "/register";

  if (isLocalPath) {
    const staffOnly = from.startsWith("/staff");
    const hikerOnly =
      from.startsWith("/booking") ||
      from.startsWith("/availability") ||
      from.startsWith("/reservation-detail");
    if (staffOnly && !isStaff(user)) return homePathFor();
    if (hikerOnly && user.role !== ROLES.HIKER) return homePathFor();
    return from;
  }

  return homePathFor();
}
