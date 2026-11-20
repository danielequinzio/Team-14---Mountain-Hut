import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Landing from "./pages/Landing";
import Availability from "./pages/Availability";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Booking from "./pages/Booking";
import MyBookings from "./pages/MyBookings";
import ChangeBooking from "./pages/ChangeBooking";
import ReservationDetail from "./pages/ReservationDetail";
import StaffSlots from "./pages/StaffSlots";
import RequireRole from "./auth/RequireRole";
import StaffRedirect from "./auth/StaffRedirect";
import { ROLES, STAFF_ROLES } from "./auth/roles";
import DefineSlot from "./pages/DefineSlot";
import CreateHiker from "./pages/CreateHiker";
import ReserveForHiker from "./pages/ReserveForHiker";
import ChangePassword from "./pages/ChangePassword";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/availability" element={<Availability />} />
      <Route path="/login" element={<Login />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/register" element={<Register />} />
      {/* booking needs a login: staff are sent to their own page, visitors to /login */}
      <Route
        path="/booking"
        element={
          <StaffRedirect to="/staff/slots">
            <RequireRole roles={[ROLES.HIKER]}>
              <Booking />
            </RequireRole>
          </StaffRedirect>
        }
      />
      <Route 
        path="/my-bookings"
        element={
          <RequireRole roles={[ROLES.HIKER]}>
            <MyBookings />
          </RequireRole>} />
      <Route
        path="/my-bookings/edit"
        element={
          <RequireRole roles={[ROLES.HIKER]}>
            <ChangeBooking />
          </RequireRole>
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
      <Route
        path="/staff/create-hiker"
        element={
          <RequireRole roles={STAFF_ROLES}>
            <CreateHiker />
          </RequireRole>
        }
      />
      <Route
        path="/staff/reserve"
        element={
          <RequireRole roles={STAFF_ROLES}>
            <ReserveForHiker />
          </RequireRole>
        }
      />
      {/* any logged-in role (hiker, employee, warden) may change their own password */}
      <Route
        path="/account/password"
        element={
          <RequireRole>
            <ChangePassword />
          </RequireRole>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
