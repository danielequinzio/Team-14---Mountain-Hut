import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import DefineSlot from "./pages/DefineSlot";

export default function App() {
  return (
    <Routes>
      <Route path="/define-slot" element={<DefineSlot />} />
      <Route path="/" element={<Navigate to="/define-slot" replace />} />
      <Route path="*" element={<Navigate to="/define-slot" replace />} />
    </Routes>
  );
}
