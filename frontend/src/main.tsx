import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ThemeProvider } from "@/theme/ThemeContext";
import { AlertsProvider } from "@/alerts/AlertsContext";
import { AuthProvider } from "@/auth/AuthContext";
import { App } from "@/App";
import "@/styles/global.css";

// No <StrictMode>: its dev-only double-invoke of effects fires every mount-time
// request twice (/me, notification history, FCM register, WS connect). The app's
// effects are already cleanup-safe, so the probe only adds duplicate network noise.
createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <ThemeProvider>
      <AlertsProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </AlertsProvider>
    </ThemeProvider>
  </BrowserRouter>,
);
