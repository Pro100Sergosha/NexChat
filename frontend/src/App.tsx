import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { LoginPage } from "@/pages/Login/Login";
import { ChatPage } from "@/pages/Chat/Chat";
import { VerifyEmailPage } from "@/pages/VerifyEmail/VerifyEmail";
import { BootScreen } from "@/components/BootScreen/BootScreen";

export function App() {
  const { phase } = useAuth();

  if (phase === "loading") return <BootScreen />;

  return (
    <Routes>
      {/* Reached from the emailed link — open to anyone regardless of session. */}
      <Route path="/verify-email" element={<VerifyEmailPage />} />
      <Route
        path="/login"
        element={phase === "authed" ? <Navigate to="/" replace /> : <LoginPage />}
      />
      <Route
        path="/"
        element={phase === "authed" ? <ChatPage /> : <Navigate to="/login" replace />}
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
