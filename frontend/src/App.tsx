import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { DashboardPage } from "@/pages/DashboardPage";
import { EmployeesPage } from "@/pages/EmployeesPage";
import { AttendancePage } from "@/pages/AttendancePage";
import { TerminalsPage } from "@/pages/TerminalsPage";
import { PrivacyPage } from "@/pages/PrivacyPage";
import { KioskPage } from "@/pages/KioskPage";
import { LoginPage } from "@/pages/LoginPage";
import { EventsPage } from "@/pages/EventsPage";
import { BlockedPage } from "@/pages/BlockedPage";
import { SchedulesPage } from "@/pages/SchedulesPage";

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem("access_token");
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <AppLayout>{children}</AppLayout>;
}

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/kiosk" element={<KioskPage />} />
        <Route
          path="/"
          element={
            <PrivateRoute>
              <DashboardPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/employees"
          element={
            <PrivateRoute>
              <EmployeesPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/schedules"
          element={
            <PrivateRoute>
              <SchedulesPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/events"
          element={
            <PrivateRoute>
              <EventsPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/blocked"
          element={
            <PrivateRoute>
              <BlockedPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/attendance"
          element={
            <PrivateRoute>
              <AttendancePage />
            </PrivateRoute>
          }
        />
        <Route
          path="/terminals"
          element={
            <PrivateRoute>
              <TerminalsPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/reports"
          element={
            <PrivateRoute>
              <AttendancePage />
            </PrivateRoute>
          }
        />
        <Route
          path="/privacy"
          element={
            <PrivateRoute>
              <PrivacyPage />
            </PrivateRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
