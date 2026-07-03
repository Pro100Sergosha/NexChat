import { useState, type FormEvent } from "react";
import { useAuth } from "@/auth/AuthContext";
import { ApiError } from "@/core/api";
import { ThemeToggle } from "@/components/ThemeToggle/ThemeToggle";
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

          <label className={styles.field}>
            <span className="op-label">Password</span>
            <input
              type="password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              required
              minLength={mode === "register" ? 8 : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={mode === "register" ? "8+ characters" : "••••••••"}
            />
          </label>

          <button className={styles.connect} type="submit" disabled={busy}>
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
