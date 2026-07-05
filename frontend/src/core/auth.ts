import { API_AUTH, apiFetch, ApiError } from "./api";
import { clearTokens, getRefresh, setTokens } from "./tokens";
import type { TokenPair, UserResponse } from "./types";

/**
 * Register a new account. The account starts unverified — the backend gates
 * /login on a confirmed email, so we do NOT log in here. The caller shows a
 * "check your inbox" screen; the user completes /verify-email from the link.
 */
export function register(
  email: string,
  username: string,
  password: string,
): Promise<UserResponse> {
  return apiFetch<UserResponse>(`${API_AUTH}/register`, {
    method: "POST",
    auth: false,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, username, password }),
  });
}

/** Redeem a single-use verify token from the emailed link → 204. */
export function verifyEmail(token: string): Promise<void> {
  return apiFetch<void>(`${API_AUTH}/verify-email`, {
    method: "POST",
    auth: false,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
}

/** Re-send the verification email. Always 202 (never reveals if the address exists). */
export function resendVerification(email: string): Promise<void> {
  return apiFetch<void>(`${API_AUTH}/resend-verification`, {
    method: "POST",
    auth: false,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
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

/**
 * Change the password for the logged-in caller. The backend mints a fresh pair
 * (the caller stays logged in even when other sessions are revoked), so we swap
 * the stored tokens. Wrong current password → ApiError `invalid_credentials`.
 */
export async function changePassword(
  currentPassword: string,
  newPassword: string,
  logoutOtherSessions: boolean,
): Promise<void> {
  const pair = await apiFetch<TokenPair>(`${API_AUTH}/change-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
      logout_other_sessions: logoutOtherSessions,
    }),
  });
  setTokens(pair);
}

/** Request a reset link. Always 202 (never reveals whether the address exists). */
export function forgotPassword(email: string): Promise<void> {
  return apiFetch<void>(`${API_AUTH}/forgot-password`, {
    method: "POST",
    auth: false,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
}

/** Redeem a single-use reset token from the emailed link → 204. */
export function resetPassword(token: string, newPassword: string): Promise<void> {
  return apiFetch<void>(`${API_AUTH}/reset-password`, {
    method: "POST",
    auth: false,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password: newPassword }),
  });
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
