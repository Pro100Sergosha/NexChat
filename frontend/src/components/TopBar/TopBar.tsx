import { shortId } from "@/core/format";
import { ThemeToggle } from "@/components/ThemeToggle/ThemeToggle";
import styles from "./TopBar.module.css";

interface Props {
  meId: string;
  meEmail: string;
  onLogout: () => void;
}

/** App header: brand, the caller's own id (for sharing), theme + logout. */
export function TopBar({ meId, meEmail, onLogout }: Props) {
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
        <div className={styles.you} title={`${meEmail} · ${meId}`}>
          <span className="op-label">You</span>
          <code className={styles.youId}>{shortId(meId)}</code>
        </div>
        <ThemeToggle />
        <button className={styles.logout} onClick={onLogout} type="button">
          <span aria-hidden>⏻</span> Log out
        </button>
      </div>
    </header>
  );
}
