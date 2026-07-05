import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError } from "@/core/api";
import { resetPassword } from "@/core/auth";
import { evaluatePassword } from "@/core/password";
import { ThemeToggle } from "@/components/ThemeToggle/ThemeToggle";
import { PasswordField } from "@/components/PasswordField/PasswordField";
import { PasswordStrength } from "@/components/PasswordStrength/PasswordStrength";
import styles from "./ResetPassword.module.css";

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token");

  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ready = evaluatePassword(password).allMet;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!token) {
      setError("This link is missing its token. Request a fresh one.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await resetPassword(token, password);
      setDone(true);
    } catch (err) {
      // Spent link → token_revoked; expired/forged/wrong-type → 401.
      setError(
        err instanceof ApiError
          ? `${err.message}. Request a fresh reset link.`
          : "Exchange unreachable. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className={styles.screen}>
      <div className={styles.themeCorner}>
        <ThemeToggle />
      </div>

      <section className={styles.plate}>
        <header className={styles.head}>
          <span className="op-label">Nexchat Exchange</span>
          <h1 className={styles.title}>Reset password</h1>
        </header>

        {done ? (
          <>
            <p className={styles.body}>
              <span className={styles.ok}>✓</span> Password updated. All other
              sessions were signed out.
            </p>
            <Link className={styles.cta} to="/login">
              Sign in
            </Link>
          </>
        ) : (
          <form className={styles.form} onSubmit={submit}>
            <div className={styles.field}>
              <label className="op-label" htmlFor="new-password">
                New password
              </label>
              <PasswordField
                id="new-password"
                autoComplete="new-password"
                minLength={8}
                value={password}
                onChange={setPassword}
                placeholder="8+ characters"
              />
              {password.length > 0 && <PasswordStrength password={password} />}
            </div>

            <button className={styles.cta} type="submit" disabled={busy || !ready}>
              Set new password
            </button>

            {error && (
              <p className={styles.bodyError} role="status" aria-live="polite">
                <span aria-hidden>›</span> {error}
              </p>
            )}

            <Link className={styles.linkBtn} to="/login">
              ‹ Back to sign in
            </Link>
          </form>
        )}
      </section>
    </main>
  );
}
