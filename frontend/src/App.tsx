import { Routes, Route } from "react-router-dom";
import AppLayout from "@/components/layout/AppLayout";
import MessagesPage from "@/pages/MessagesPage";
import DashboardPage from "@/pages/DashboardPage";
import NotFoundPage from "@/pages/NotFoundPage";

export default function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <AppLayout title="Сообщения">
            <MessagesPage />
          </AppLayout>
        }
      />
      <Route
        path="/dashboard"
        element={
          <AppLayout title="Аналитика">
            <DashboardPage />
          </AppLayout>
        }
      />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
