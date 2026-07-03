import { useState, type FormEvent } from "react";
import type { ConversationOut } from "@/core/types";
import { railTime, shortId } from "@/core/format";
import styles from "./LineRail.module.css";

interface Props {
  conversations: ConversationOut[];
  activeId: number | null;
  meId: string;
  meEmail: string;
  onSelect: (id: number) => void;
  onNewLine: (recipientId: string) => void;
  onLogout: () => void;
}

export function LineRail({
  conversations,
  activeId,
  meId,
  meEmail,
  onSelect,
  onNewLine,
  onLogout,
}: Props) {
  const [opening, setOpening] = useState(false);
  const [recipient, setRecipient] = useState("");

  function submitNewLine(e: FormEvent) {
    e.preventDefault();
    const id = recipient.trim();
    if (!id) return;
    onNewLine(id);
    setRecipient("");
    setOpening(false);
  }

  return (
    <aside className={styles.rail}>
      <div className={styles.railHead}>
        <span className="op-label">Open lines</span>
        <button
          className={styles.newBtn}
          onClick={() => setOpening((v) => !v)}
          type="button"
          aria-expanded={opening}
        >
          {opening ? "×" : "+ New line"}
        </button>
      </div>

      {opening && (
        <form className={styles.newForm} onSubmit={submitNewLine}>
          <label className="op-label" htmlFor="recip">
            Party user id
          </label>
          <input
            id="recip"
            className={styles.newInput}
            value={recipient}
            onChange={(e) => setRecipient(e.target.value)}
            placeholder="paste the other party's id"
            autoComplete="off"
            autoFocus
          />
          <button className={styles.openBtn} type="submit">
            Open line
          </button>
        </form>
      )}

      <ul className={styles.list}>
        {conversations.length === 0 && (
          <li className={styles.empty}>
            No open lines yet. Share your id and open one.
          </li>
        )}
        {conversations.map((c) => {
          const on = c.id === activeId;
          return (
            <li key={c.id}>
              <button
                className={on ? styles.rowOn : styles.row}
                onClick={() => onSelect(c.id)}
                type="button"
                aria-current={on}
              >
                <span className={styles.rowMark} aria-hidden>
                  {on ? "●" : "○"}
                </span>
                <span className={styles.rowChannel}>
                  CH.{String(c.id).padStart(3, "0")}
                </span>
                <span className={styles.rowParty}>{shortId(c.other_user_id)}</span>
                <span className={styles.rowTime}>{railTime(c.last_message_at)}</span>
              </button>
            </li>
          );
        })}
      </ul>

      <footer className={styles.footer}>
        <div className={styles.you}>
          <span className="op-label">You</span>
          <code className={styles.youId} title={`${meEmail} · ${meId}`}>
            {shortId(meId)}
          </code>
        </div>
        <button className={styles.logout} onClick={onLogout} type="button" title="Log out">
          ⏻ Log out
        </button>
      </footer>
    </aside>
  );
}
