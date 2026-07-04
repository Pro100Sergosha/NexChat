import { useAlerts } from "@/alerts/AlertsContext";
import styles from "./AlertsToggle.module.css";

/** Enables/mutes new-message sound and desktop notifications. */
export function AlertsToggle() {
  const { enabled, toggle } = useAlerts();
  return (
    <button
      className={styles.toggle}
      onClick={toggle}
      type="button"
      aria-pressed={enabled}
      title={enabled ? "Mute alerts" : "Enable alerts"}
      aria-label={enabled ? "Mute alerts" : "Enable alerts"}
    >
      <span className={styles.glyph} aria-hidden>
        {enabled ? "🔔" : "🔕"}
      </span>
      <span className={styles.label}>{enabled ? "on" : "off"}</span>
    </button>
  );
}
