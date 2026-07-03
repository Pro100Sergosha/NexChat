import { useState } from "react";
import { PASSWORD_MAX } from "@/core/password";
import styles from "./PasswordField.module.css";

interface Props {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: string;
  placeholder?: string;
  minLength?: number;
  required?: boolean;
}

/** Password input with an inline show/hide toggle. */
export function PasswordField({
  id,
  value,
  onChange,
  autoComplete,
  placeholder,
  minLength,
  required = true,
}: Props) {
  const [show, setShow] = useState(false);
  return (
    <div className={styles.wrap}>
      <input
        id={id}
        className={styles.input}
        type={show ? "text" : "password"}
        value={value}
        autoComplete={autoComplete}
        placeholder={placeholder}
        minLength={minLength}
        maxLength={PASSWORD_MAX}
        required={required}
        onChange={(e) => onChange(e.target.value)}
      />
      <button
        type="button"
        className={styles.toggle}
        onClick={() => setShow((s) => !s)}
        aria-pressed={show}
        aria-label={show ? "Hide password" : "Show password"}
      >
        {show ? "Hide" : "Show"}
      </button>
    </div>
  );
}
