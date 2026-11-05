import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Landing from "./pages/Landing";
import Availability from "./pages/Availability";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Booking from "./pages/Booking";
import ReservationDetail from "./pages/ReservationDetail";
import StaffSlots from "./pages/StaffSlots";
import RequireRole from "./auth/RequireRole";
import StaffRedirect from "./auth/StaffRedirect";
import { ROLES, STAFF_ROLES } from "./auth/roles";
import DefineSlot from "./pages/DefineSlot";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/availability" element={<Availability />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      {/* availability is public: visitors and hikers may look, staff are sent to their own page */}
      <Route
        path="/booking"
        element={
          <StaffRedirect to="/staff/slots">
            <Booking />
          </StaffRedirect>
        }
      />
      <Route
        path="/reservation-detail"
        element={
          <RequireRole roles={[ROLES.HIKER]}>
            <ReservationDetail />
          </RequireRole>
        }
      />
      <Route
        path="/staff/slots"
        element={
          <RequireRole roles={STAFF_ROLES}>
            <StaffSlots />
          </RequireRole>
        }
      />
      <Route
        path="/staff/define-slot"
        element={
          <RequireRole roles={STAFF_ROLES}>
            <DefineSlot />
          </RequireRole>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
