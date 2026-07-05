import { useEffect, useState, type FormEvent } from "react";
import { ApiError } from "@/core/api";
import { changePassword } from "@/core/auth";
import { evaluatePassword } from "@/core/password";
import { PasswordField } from "@/components/PasswordField/PasswordField";
import { PasswordStrength } from "@/components/PasswordStrength/PasswordStrength";
import styles from "./AccountPanel.module.css";

interface Props {
  onClose: () => void;
}

/** Account settings dialog — currently hosts the change-password form. */
export function AccountPanel({ onClose }: Props) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [logoutOthers, setLogoutOthers] = useState(true);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Esc closes, matching the overlay click.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const ready = current.length > 0 && evaluatePassword(next).allMet;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await changePassword(current, next, logoutOthers);
      setDone(true);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Exchange unreachable. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className={styles.overlay}
      role="dialog"
      aria-modal="true"
      aria-label="Account settings"
      onClick={onClose}
    >
      <section className={styles.panel} onClick={(e) => e.stopPropagation()}>
        <header className={styles.head}>
          <h2 className={styles.title}>Account</h2>
          <button
            className={styles.close}
            type="button"
            onClick={onClose}
            aria-label="Close"
          >
            ✕
          </button>
        </header>

        {done ? (
          <div className={styles.form}>
            <p className={styles.ok}>
              <span aria-hidden>✓</span>{" "}
              {logoutOthers
                ? "Password changed. Other sessions were signed out."
                : "Password changed."}
            </p>
            <button className={styles.cta} type="button" onClick={onClose}>
              Done
            </button>
          </div>
        ) : (
          <form className={styles.form} onSubmit={submit}>
            <div className={styles.field}>
              <label className="op-label" htmlFor="current-password">
                Current password
              </label>
              <PasswordField
                id="current-password"
                autoComplete="current-password"
                value={current}
                onChange={setCurrent}
                placeholder="••••••••"
              />
            </div>

            <div className={styles.field}>
              <label className="op-label" htmlFor="new-password">
                New password
              </label>
              <PasswordField
                id="new-password"
                autoComplete="new-password"
                minLength={8}
                value={next}
                onChange={setNext}
                placeholder="8+ characters"
              />
              {next.length > 0 && <PasswordStrength password={next} />}
            </div>

            <label className={styles.check}>
              <input
                type="checkbox"
                checked={logoutOthers}
                onChange={(e) => setLogoutOthers(e.target.checked)}
              />
              <span>Sign out other devices</span>
            </label>

            <button className={styles.cta} type="submit" disabled={busy || !ready}>
              Change password
            </button>

            {error && (
              <p className={styles.error} role="status" aria-live="polite">
                <span aria-hidden>›</span> {error}
              </p>
            )}
          </form>
        )}
      </section>
    </div>
  );
}
