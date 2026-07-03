import { useState, type FormEvent, type KeyboardEvent } from "react";
import styles from "./Composer.module.css";

const MAX = 4000;

interface Props {
  disabled: boolean;
  hint: string;
  onSend: (text: string) => void;
}

export function Composer({ disabled, hint, onSend }: Props) {
  const [text, setText] = useState("");

  function fire() {
    const content = text.trim();
    if (!content || disabled) return;
    onSend(content);
    setText("");
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    fire();
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends; Shift+Enter inserts a newline.
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      fire();
    }
  }

  const over = text.length > MAX;

  return (
    <form className={styles.composer} onSubmit={onSubmit}>
      <span className={styles.prompt} aria-hidden>
        ›
      </span>
      <textarea
        className={styles.input}
        rows={1}
        value={text}
        maxLength={MAX + 200}
        disabled={disabled}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKey}
        placeholder={disabled ? "Line not connected…" : hint}
        aria-label="Message"
      />
      {text.length > MAX - 200 && (
        <span className={over ? styles.countOver : styles.count}>
          {MAX - text.length}
        </span>
      )}
      <button className={styles.send} type="submit" disabled={disabled || over || !text.trim()}>
        Send
      </button>
    </form>
  );
}
