import { useEffect, useRef } from "react";
import type { ChatMessage } from "@/core/types";
import { msgTime } from "@/core/format";
import styles from "./Transcript.module.css";

interface Props {
  messages: ChatMessage[];
  meId: string;
  emptyHint: string;
}

export function Transcript({ messages, meId, emptyHint }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  // Keep the newest line in view as the transcript grows.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length]);

  return (
    <div className={styles.scroll}>
      {messages.length === 0 ? (
        <p className={styles.empty}>{emptyHint}</p>
      ) : (
        <ol className={styles.log}>
          {messages.map((m) => {
            const mine = m.sender_id === meId;
            return (
              <li
                key={m.id}
                className={mine ? styles.mine : styles.theirs}
                data-pending={m.pending ? "" : undefined}
              >
                <div className={styles.bubble}>
                  <p className={styles.content}>{m.content}</p>
                </div>
                <div className={styles.stamp}>
                  <span className={styles.who}>{mine ? "·you" : "·incoming"}</span>
                  <time>{m.pending ? "sending…" : msgTime(m.created_at)}</time>
                </div>
              </li>
            );
          })}
        </ol>
      )}
      <div ref={endRef} />
    </div>
  );
}
