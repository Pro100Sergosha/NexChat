import type { TokenPair } from "./types";

// JWT pair lives in localStorage (per frontend spec). Access is short-lived
// (15m), refresh long-lived (7d); apiFetch rotates them transparently.
const ACCESS = "nexchat.access_token";
const REFRESH = "nexchat.refresh_token";

export function getAccess(): string | null {
  return localStorage.getItem(ACCESS);
}

export function getRefresh(): string | null {
  return localStorage.getItem(REFRESH);
}

export function setTokens(pair: TokenPair): void {
  localStorage.setItem(ACCESS, pair.access_token);
  localStorage.setItem(REFRESH, pair.refresh_token);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS);
  localStorage.removeItem(REFRESH);
}

export function hasSession(): boolean {
  return getAccess() !== null && getRefresh() !== null;
}
