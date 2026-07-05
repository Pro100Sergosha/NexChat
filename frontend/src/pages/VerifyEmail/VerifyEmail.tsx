import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError } from "@/core/api";
import { resendVerification, verifyEmail } from "@/core/auth";
import { ThemeToggle } from "@/components/ThemeToggle/ThemeToggle";
import styles from "./VerifyEmail.module.css";

type Phase = "working" | "ok" | "already" | "bad";

export function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const [phase, setPhase] = useState<Phase>("working");
  // Guard React 18 StrictMode's double-invoke — the verify token is single-use,
  // so a second POST would 409/401 against our own first, successful redemption.
  const ran = useRef(false);

  const [email, setEmail] = useState("");
  const [resendMsg, setResendMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;

    if (!token) {
      setPhase("bad");
      return;
    }
    void (async () => {
      try {
        await verifyEmail(token);
        setPhase("ok");
      } catch (err) {
        if (err instanceof ApiError && err.code === "email_already_verified") {
          setPhase("already");
        } else {
          setPhase("bad");
        }
      }
    })();
  }, [token]);

  async function resend() {
    setBusy(true);
    try {
      await resendVerification(email);
      setResendMsg("New link sent. Check your inbox.");
    } catch {
      setResendMsg("Couldn't send just now. Try again.");
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
          <h1 className={styles.title}>Verify email</h1>
        </header>

        {phase === "working" && <p className={styles.body}>Confirming your line…</p>}

        {phase === "ok" && (
          <>
            <p className={styles.body}>
              <span className={styles.ok}>✓</span> Your email is verified. The line is
              live.
            </p>
            <Link className={styles.cta} to="/login">
              Sign in
            </Link>
          </>
        )}

        {phase === "already" && (
          <>
            <p className={styles.body}>This email was already verified.</p>
            <Link className={styles.cta} to="/login">
              Sign in
            </Link>
          </>
        )}

        {phase === "bad" && (
          <>
            <p className={styles.bodyError}>
              <span aria-hidden>›</span> This link is invalid or expired. Enter your
              email to get a fresh one.
            </p>
            <div className={styles.resend}>
              <input
                className={styles.input}
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@exchange.net"
              />
              <button
                className={styles.cta}
                type="button"
                onClick={() => void resend()}
                disabled={busy || email.trim() === ""}
              >
                Send new link
              </button>
            </div>
            {resendMsg && (
              <p className={styles.note} role="status">
                {resendMsg}
              </p>
            )}
            <Link className={styles.linkBtn} to="/login">
              ‹ Back to sign in
            </Link>
          </>
        )}
      </section>
    </main>
  );
}
