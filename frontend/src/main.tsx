import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ThemeProvider } from "@/theme/ThemeContext";
import { AlertsProvider } from "@/alerts/AlertsContext";
import { AuthProvider } from "@/auth/AuthContext";
import { App } from "@/App";
import "@/styles/global.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <AlertsProvider>
          <AuthProvider>
            <App />
          </AuthProvider>
        </AlertsProvider>
      </ThemeProvider>
    </BrowserRouter>
  </StrictMode>,
);
