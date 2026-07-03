import { API_AUTH, apiFetch, ApiError } from "./api";
import { clearTokens, getRefresh, setTokens } from "./tokens";
import type { TokenPair, UserResponse } from "./types";

/** Register a new account, then log in to obtain a token pair. */
export async function register(email: string, password: string): Promise<void> {
  await apiFetch<UserResponse>(`${API_AUTH}/register`, {
    method: "POST",
    auth: false,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  await login(email, password);
}

/** OAuth2 password form: username carries the email, body is form-encoded. */
export async function login(email: string, password: string): Promise<void> {
  const form = new URLSearchParams();
  form.set("username", email);
  form.set("password", password);

  const pair = await apiFetch<TokenPair>(`${API_AUTH}/login`, {
    method: "POST",
    auth: false,
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  });
  setTokens(pair);
}

export function me(): Promise<UserResponse> {
  return apiFetch<UserResponse>(`${API_AUTH}/me`);
}

/** Revoke both tokens server-side, then drop the local session. */
export async function logout(): Promise<void> {
  const refresh_token = getRefresh();
  try {
    if (refresh_token) {
      await apiFetch<void>(`${API_AUTH}/logout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token }),
      });
    }
  } catch (err) {
    // A revoked/expired token still means "logged out" — swallow and clear.
    if (!(err instanceof ApiError)) throw err;
  } finally {
    clearTokens();
  }
}
