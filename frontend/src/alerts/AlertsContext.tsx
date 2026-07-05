import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { playPing, unlockAudio } from "@/core/sound";
import { requestNotifyPermission, showNotification } from "@/core/desktop";
import { enablePush } from "@/core/push";

const KEY = "nexchat.alerts";

interface FireOpts {
  title: string;
  body: string;
  /** Allow an OS notification (typically only when the tab is hidden). */
  desktop: boolean;
}

interface AlertsState {
  enabled: boolean;
  toggle: () => void;
  fire: (opts: FireOpts) => void;
}

const AlertsContext = createContext<AlertsState | null>(null);

export function AlertsProvider({ children }: { children: ReactNode }) {
  const [enabled, setEnabled] = useState<boolean>(() => {
    return localStorage.getItem(KEY) !== "off"; // default on
  });

  // Browsers keep audio suspended until a gesture — unlock on the first one so
  // sound works even though messages arrive without user interaction.
  useEffect(() => {
    const unlock = () => unlockAudio();
    window.addEventListener("pointerdown", unlock, { once: true });
    window.addEventListener("keydown", unlock, { once: true });
    return () => {
      window.removeEventListener("pointerdown", unlock);
      window.removeEventListener("keydown", unlock);
    };
  }, []);

  const toggle = useCallback(() => {
    setEnabled((prev) => {
      const next = !prev;
      localStorage.setItem(KEY, next ? "on" : "off");
      if (next) {
        unlockAudio();
        // Opting into alerts also opts into background push: prompt, then
        // register this browser with FCM once permission is granted.
        void requestNotifyPermission().then((granted) => {
          if (granted) void enablePush();
        });
      }
      return next;
    });
  }, []);

  const fire = useCallback(
    ({ title, body, desktop }: FireOpts) => {
      if (!enabled) return;
      playPing();
      if (desktop) showNotification(title, body);
    },
    [enabled],
  );

  const value = useMemo<AlertsState>(
    () => ({ enabled, toggle, fire }),
    [enabled, toggle, fire],
  );

  return <AlertsContext.Provider value={value}>{children}</AlertsContext.Provider>;
}

export function useAlerts(): AlertsState {
  const ctx = useContext(AlertsContext);
  if (!ctx) throw new Error("useAlerts must be used within AlertsProvider");
  return ctx;
}
