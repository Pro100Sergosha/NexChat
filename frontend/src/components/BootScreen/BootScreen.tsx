import styles from "./BootScreen.module.css";

/** Shown while an existing session is being validated on load. */
export function BootScreen() {
  return (
    <div className={styles.boot}>
      <span className={styles.dot} aria-hidden />
      <span className="op-label">Connecting to exchange…</span>
    </div>
  );
}
