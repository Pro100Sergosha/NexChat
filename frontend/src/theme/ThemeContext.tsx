import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type Theme = "light" | "dark";

const KEY = "nexchat.theme";

function stored(): Theme | null {
  const v = localStorage.getItem(KEY);
  return v === "light" || v === "dark" ? v : null;
}

function systemTheme(): Theme {
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

function apply(theme: Theme | null): void {
  const el = document.documentElement;
  if (theme) el.setAttribute("data-theme", theme);
  else el.removeAttribute("data-theme");
}

interface ThemeState {
  theme: Theme; // the currently resolved theme
  toggle: () => void;
}

const ThemeContext = createContext<ThemeState | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  // Resolve to the explicit choice if any, else the system preference.
  const [theme, setTheme] = useState<Theme>(() => stored() ?? systemTheme());

  // Reflect the stored choice on the root (absent => CSS follows the system).
  useEffect(() => {
    apply(stored());
  }, []);

  // While the user hasn't forced a theme, track live system changes.
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    const onChange = () => {
      if (!stored()) setTheme(mq.matches ? "light" : "dark");
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const toggle = useCallback(() => {
    setTheme((prev) => {
      const next: Theme = prev === "dark" ? "light" : "dark";
      localStorage.setItem(KEY, next);
      apply(next);
      return next;
    });
  }, []);

  const value = useMemo<ThemeState>(() => ({ theme, toggle }), [theme, toggle]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
