import { useTheme } from "@/theme/ThemeContext";
import styles from "./ThemeToggle.module.css";

/** Flips between the light and dark Exchange palettes. */
export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const next = theme === "dark" ? "light" : "dark";
  return (
    <button
      className={styles.toggle}
      onClick={toggle}
      type="button"
      title={`Switch to ${next} theme`}
      aria-label={`Switch to ${next} theme`}
    >
      <span className={styles.glyph} aria-hidden>
        {theme === "dark" ? "☾" : "☀"}
      </span>
      <span className={styles.label}>{theme}</span>
    </button>
  );
}
