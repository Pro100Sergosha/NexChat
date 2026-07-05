import { useState, type FormEvent } from "react";
import { useAuth } from "@/auth/AuthContext";
import { ApiError } from "@/core/api";
import { forgotPassword, resendVerification } from "@/core/auth";
import { evaluatePassword } from "@/core/password";
import { ThemeToggle } from "@/components/ThemeToggle/ThemeToggle";
import { PasswordField } from "@/components/PasswordField/PasswordField";
import { PasswordStrength } from "@/components/PasswordStrength/PasswordStrength";
import styles from "./Login.module.css";

type Mode = "login" | "register";

// Mirrors the backend rule (3–32, lowercase letters/digits/underscore) so we
// can gate the button before a round-trip; the server re-validates regardless.
const USERNAME_RE = /^[a-z0-9_]{3,32}$/;

export function LoginPage() {
  const { signIn, signUp } = useAuth();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [readout, setReadout] = useState<string | null>(null);
  const [error, setError] = useState(false);
  // After a successful register we swap the form for a "check your inbox" panel.
  const [sent, setSent] = useState(false);
  // login gated by an unverified email → offer to re-send the link.
  const [unverified, setUnverified] = useState(false);
  // forgot-password sub-view (email → reset link), and its post-submit ack.
  const [forgot, setForgot] = useState(false);
  const [forgotSent, setForgotSent] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(false);
    setUnverified(false);
    setReadout(mode === "login" ? "Placing call…" : "Opening account…");
    try {
      if (mode === "login") {
        await signIn(email, password);
        // On success the auth phase flips and the router leaves this page.
      } else {
        await signUp(email, username, password);
        setSent(true);
      }
    } catch (err) {
      setError(true);
      if (err instanceof ApiError && err.code === "email_not_verified") {
        setUnverified(true);
      }
      setReadout(
        err instanceof ApiError ? err.message : "Exchange unreachable. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    setBusy(true);
    try {
      await resendVerification(email);
      setError(false);
      setUnverified(false);
      setReadout("Verification re-sent. Check your inbox.");
    } catch {
      setError(true);
      setReadout("Couldn't re-send just now. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function submitForgot(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await forgotPassword(email);
    } catch {
      // Anti-enumeration: the response is identical regardless — even a network
      // hiccup shouldn't hint at existence, so we ack the same way.
    } finally {
      setBusy(false);
      setForgotSent(true);
    }
  }

  function openForgot() {
    setForgot(true);
    setForgotSent(false);
    setError(false);
    setUnverified(false);
    setReadout(null);
  }

  function switchMode(next: Mode) {
    if (next === mode) return;
    setMode(next);
    setError(false);
    setUnverified(false);
    setReadout(null);
  }

  function backToSignIn() {
    setSent(false);
    setForgot(false);
    setForgotSent(false);
    setMode("login");
    setPassword("");
    setError(false);
    setReadout(null);
  }

  // Registration is gated on the client password + username policy; sign-in isn't.
  const registerReady =
    mode === "login" ||
    (evaluatePassword(password).allMet && USERNAME_RE.test(username.trim()));

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

        {forgot ? (
          forgotSent ? (
            <div className={styles.form}>
              <p className={styles.sent}>
                If an account exists for{" "}
                <code className={styles.sentAddr}>{email}</code>, a reset link is on
                its way. Open it to choose a new password.
              </p>
              <button className={styles.linkBtn} type="button" onClick={backToSignIn}>
                ‹ Back to sign in
              </button>
            </div>
          ) : (
            <form className={styles.form} onSubmit={submitForgot}>
              <p className={styles.sent}>
                Enter your email and we&apos;ll send a link to reset your password.
              </p>
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
              <button className={styles.connect} type="submit" disabled={busy}>
                Send reset link
              </button>
              <button className={styles.linkBtn} type="button" onClick={backToSignIn}>
                ‹ Back to sign in
              </button>
            </form>
          )
        ) : sent ? (
          <div className={styles.form}>
            <p className={styles.sent}>
              Verification link sent to <code className={styles.sentAddr}>{email}</code>.
              Open it to activate your line, then sign in.
            </p>
            <button
              className={styles.connect}
              type="button"
              onClick={() => void resend()}
              disabled={busy}
            >
              Re-send link
            </button>
            <button className={styles.linkBtn} type="button" onClick={backToSignIn}>
              ‹ Back to sign in
            </button>
          </div>
        ) : (
          <>
            <div
              className={styles.tabs}
              data-mode={mode}
              role="tablist"
              aria-label="Access mode"
            >
              <span className={styles.indicator} aria-hidden />
              <button
                role="tab"
                aria-selected={mode === "login"}
                className={styles.tab}
                onClick={() => switchMode("login")}
                type="button"
              >
                Sign in
              </button>
              <button
                role="tab"
                aria-selected={mode === "register"}
                className={styles.tab}
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

              {mode === "register" && (
                <label className={styles.field}>
                  <span className="op-label">Username</span>
                  <input
                    type="text"
                    autoComplete="username"
                    required
                    value={username}
                    onChange={(e) => setUsername(e.target.value.toLowerCase())}
                    minLength={3}
                    maxLength={32}
                    pattern="[a-z0-9_]{3,32}"
                    placeholder="a-z, 0-9, _"
                  />
                </label>
              )}

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
                <div
                  className={styles.reveal}
                  data-open={
                    mode === "register" && password.length > 0 ? "" : undefined
                  }
                >
                  <div className={styles.revealInner}>
                    <PasswordStrength password={password} />
                  </div>
                </div>
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
              {readout ??
                (mode === "login" ? "Awaiting credentials." : "Choose your line.")}
            </p>

            {unverified && (
              <button
                className={styles.linkBtn}
                type="button"
                onClick={() => void resend()}
                disabled={busy}
              >
                Re-send verification link
              </button>
            )}

            {mode === "login" && !unverified && (
              <button className={styles.linkBtn} type="button" onClick={openForgot}>
                Forgot password?
              </button>
            )}
          </>
        )}
      </section>
    </main>
  );
}
