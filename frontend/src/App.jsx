import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Booking from "./pages/Booking";
import ReservationDetail from "./pages/ReservationDetail";

export default function App() {
  return (
    <Routes>
      <Route path="/booking" element={<Booking />} />
      <Route path="/reservation-detail" element={<ReservationDetail />} />
      <Route path="/" element={<Navigate to="/booking" replace />} />
      <Route path="*" element={<Navigate to="/booking" replace />} />
    </Routes>
  );
}
