/** User ids are UUIDs — show a short, monospace-friendly stub. */
export function shortId(id: string): string {
  const head = id.replace(/-/g, "").slice(0, 4);
  return head ? `${head}…` : "—";
}

/** Timestamp for the rail: HH:MM today, weekday this week, else DD.MM. */
export function railTime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) return hhmm(d);
  const days = (now.getTime() - d.getTime()) / 86_400_000;
  if (days < 7) return d.toLocaleDateString([], { weekday: "short" });
  return d.toLocaleDateString([], { day: "2-digit", month: "2-digit" });
}

/** Timestamp for a transcript line. */
export function msgTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : hhmm(d);
}

function hhmm(d: Date): string {
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
}
