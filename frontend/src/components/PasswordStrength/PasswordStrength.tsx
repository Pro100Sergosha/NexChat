import { evaluatePassword, PASSWORD_REQUIREMENTS } from "@/core/password";
import styles from "./PasswordStrength.module.css";

/**
 * Live password gauge for registration: a signal-strength meter plus the
 * requirement checklist, updating as the user types.
 */
export function PasswordStrength({ password }: { password: string }) {
  const { checks, score, label } = evaluatePassword(password);

  return (
    <div className={styles.wrap} aria-live="polite">
      <div className={styles.meterRow}>
        <div className={styles.meter} data-score={score}>
          {[1, 2, 3, 4].map((i) => (
            <span
              key={i}
              className={styles.seg}
              data-on={i <= score ? "" : undefined}
            />
          ))}
        </div>
        <span className={styles.label} data-score={score}>
          {label}
        </span>
      </div>

      <ul className={styles.reqs}>
        {PASSWORD_REQUIREMENTS.map((r) => {
          const met = checks[r.key];
          return (
            <li key={r.key} className={met ? styles.met : styles.unmet}>
              <span className={styles.mark} aria-hidden>
                {met ? "✓" : "○"}
              </span>
              {r.label}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
