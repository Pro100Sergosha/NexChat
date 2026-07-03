// Client-side password policy for registration. The backend currently only
// enforces length (8–128), but the intended policy (and what we surface here)
// also requires an uppercase letter, a digit and a special character. Since
// this is a stricter superset, anything accepted here is accepted by the
// backend too.
export const PASSWORD_MIN = 8;
export const PASSWORD_MAX = 128;

export type ReqKey = "length" | "upper" | "digit" | "symbol";

export const PASSWORD_REQUIREMENTS: { key: ReqKey; label: string }[] = [
  { key: "length", label: "At least 8 characters" },
  { key: "upper", label: "An uppercase letter" },
  { key: "digit", label: "A number" },
  { key: "symbol", label: "A special character" },
];

const STRENGTH_LABELS = ["Weak", "Weak", "Fair", "Good", "Strong"] as const;

export interface PasswordEval {
  checks: Record<ReqKey, boolean>;
  allMet: boolean;
  score: number; // 0..4, drives the meter
  label: string;
}

export function evaluatePassword(pw: string): PasswordEval {
  const checks: Record<ReqKey, boolean> = {
    length: pw.length >= PASSWORD_MIN,
    upper: /[A-Z]/.test(pw),
    digit: /\d/.test(pw),
    symbol: /[^A-Za-z0-9]/.test(pw),
  };
  const metCount = Object.values(checks).filter(Boolean).length;
  const allMet = metCount === PASSWORD_REQUIREMENTS.length;

  // Score tracks requirements met; a long password that meets them all reads
  // as full strength.
  let score = metCount;
  if (allMet && pw.length >= 12) score = 4;

  return { checks, allMet, score, label: STRENGTH_LABELS[score] ?? "Weak" };
}