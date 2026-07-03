import type { LineStatus } from "@/core/ws";
import styles from "./LiveLine.module.css";

const LABEL: Record<LineStatus, string> = {
  open: "Live",
  connecting: "Connecting",
  reconnecting: "Reconnecting",
  closed: "Off line",
};

interface Props {
  status: LineStatus;
  channelLabel: string;
  party: string;
  /** Increment to fire a single traveling pulse (a frame going down the wire). */
  pulseKey: number;
}

/**
 * The signature element. A horizontal line under the conversation header that
 * is a solid glowing cyan when the socket is open and a dim brass dash when
 * it isn't — a direct readout of ws.readyState. A pulse travels the line only
 * when a message is actually sent, not ambiently.
 */
export function LiveLine({ status, channelLabel, party, pulseKey }: Props) {
  const live = status === "open";
  return (
    <header className={styles.head}>
      <div className={styles.meta}>
        <span className={styles.channel}>{channelLabel}</span>
        <span className={styles.party}>party {party}</span>
        <span
          className={live ? styles.badgeLive : styles.badge}
          data-status={status}
        >
          <span className={styles.dot} aria-hidden />
          {LABEL[status]}
        </span>
      </div>
      <div className={styles.line} data-status={status} aria-hidden>
        {live && pulseKey > 0 && <span key={pulseKey} className={styles.pulse} />}
      </div>
    </header>
  );
}
