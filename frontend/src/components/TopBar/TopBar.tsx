import { useState } from "react";
import { shortId } from "@/core/format";
import { ThemeToggle } from "@/components/ThemeToggle/ThemeToggle";
import { AlertsToggle } from "@/components/AlertsToggle/AlertsToggle";
import { NotificationsBell } from "@/components/NotificationsBell/NotificationsBell";
import { AccountPanel } from "@/components/AccountPanel/AccountPanel";
import styles from "./TopBar.module.css";

interface Props {
  meId: string;
  meName: string;
  meEmail: string;
  onLogout: () => void;
}

/** App header: brand, the caller's own id (for sharing), theme + logout. */
export function TopBar({ meId, meName, meEmail, onLogout }: Props) {
  const [account, setAccount] = useState(false);
  return (
    <header className={styles.bar}>
      <div className={styles.brand}>
        <span className={styles.mark} aria-hidden>
          ▚
        </span>
        <span className={styles.name}>NexChat</span>
        <span className="op-label">Exchange</span>
      </div>

      <div className={styles.controls}>
        <div className={styles.you} title={`${meName} · ${meEmail} · ${meId}`}>
          <span className="op-label">You</span>
          <code className={styles.youId}>@{meName}</code>
          <code className={styles.youUuid}>{shortId(meId)}</code>
        </div>
        <NotificationsBell />
        <AlertsToggle />
        <ThemeToggle />
        <button
          className={styles.settings}
          onClick={() => setAccount(true)}
          type="button"
          aria-label="Account settings"
        >
          <span aria-hidden>⚙</span>
        </button>
        <button className={styles.logout} onClick={onLogout} type="button">
          <span aria-hidden>⏻</span> Log out
        </button>
      </div>

      {account && <AccountPanel onClose={() => setAccount(false)} />}
    </header>
  );
}
