import { useState, type FormEvent } from "react";
import { useAuth } from "@/auth/AuthContext";
import { ApiError } from "@/core/api";
import { evaluatePassword } from "@/core/password";
import { ThemeToggle } from "@/components/ThemeToggle/ThemeToggle";
import { PasswordField } from "@/components/PasswordField/PasswordField";
import { PasswordStrength } from "@/components/PasswordStrength/PasswordStrength";
import styles from "./Login.module.css";

type Mode = "login" | "register";

export function LoginPage() {
  const { signIn, signUp } = useAuth();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [readout, setReadout] = useState<string | null>(null);
  const [error, setError] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(false);
    setReadout(mode === "login" ? "Placing call…" : "Opening account…");
    try {
      if (mode === "login") await signIn(email, password);
      else await signUp(email, password);
      // On success the auth phase flips and the router leaves this page.
    } catch (err) {
      setError(true);
      setReadout(
        err instanceof ApiError ? err.message : "Exchange unreachable. Try again.",
      );
      setBusy(false);
    }
  }

  function switchMode(next: Mode) {
    if (next === mode) return;
    setMode(next);
    setError(false);
    setReadout(null);
  }

  // Registration is gated on the client password policy; sign-in isn't.
  const registerReady = mode === "login" || evaluatePassword(password).allMet;

  return (
    <main className={styles.screen}>
      <div className={styles.themeCorner}>
        <ThemeToggle />
      </div>

      <section className={styles.plate} aria-labelledby="plate-title">
        <header className={styles.plateHead}>
          <span className="op-label">Nexchat Exchange</span>
          <h1 id="plate-title" className={styles.title}>
            Operator
          </h1>
          <p className={styles.sub}>Patch into the line.</p>
        </header>

        <div className={styles.tabs} role="tablist" aria-label="Access mode">
          <button
            role="tab"
            aria-selected={mode === "login"}
            className={mode === "login" ? styles.tabOn : styles.tab}
            onClick={() => switchMode("login")}
            type="button"
          >
            Sign in
          </button>
          <button
            role="tab"
            aria-selected={mode === "register"}
            className={mode === "register" ? styles.tabOn : styles.tab}
            onClick={() => switchMode("register")}
            type="button"
          >
            New account
          </button>
        </div>

        <form className={styles.form} onSubmit={submit}>
          <label className={styles.field}>
            <span className="op-label">Email</span>
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@exchange.net"
            />
          </label>

          <div className={styles.field}>
            <label className="op-label" htmlFor="password">
              Password
            </label>
            <PasswordField
              id="password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              minLength={mode === "register" ? 8 : undefined}
              value={password}
              onChange={setPassword}
              placeholder={mode === "register" ? "8+ characters" : "••••••••"}
            />
            {mode === "register" && password.length > 0 && (
              <PasswordStrength password={password} />
            )}
          </div>

          <button
            className={styles.connect}
            type="submit"
            disabled={busy || !registerReady}
          >
            {mode === "login" ? "Connect" : "Open line"}
          </button>
        </form>

        <p
          className={error ? styles.readoutError : styles.readout}
          role="status"
          aria-live="polite"
        >
          <span className={styles.readoutMark} aria-hidden>
            ›
          </span>
          {readout ?? (mode === "login" ? "Awaiting credentials." : "Choose your line.")}
        </p>
      </section>
    </main>
  );
}
