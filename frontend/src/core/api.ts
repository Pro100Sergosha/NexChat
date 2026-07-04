import type { ApiErrorBody, TokenPair } from "./types";
import { clearTokens, getAccess, getRefresh, setTokens } from "./tokens";

export const API_AUTH = "/api/auth";
export const API_CHAT = "/api/chat";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function parseError(res: Response): Promise<ApiError> {
  let code = "http_error";
  let message = `Request failed (${res.status})`;
  try {
    const body = (await res.json()) as Partial<ApiErrorBody>;
    if (body.code) code = body.code;
    if (body.message) message = body.message;
  } catch {
    /* non-JSON body — keep defaults */
  }
  return new ApiError(res.status, code, message);
}

// Single in-flight refresh shared by concurrent 401s, so we rotate the refresh
// token exactly once (it is single-use — the backend revokes it on /refresh).
let refreshing: Promise<boolean> | null = null;

export async function refreshTokens(): Promise<boolean> {
  const refresh_token = getRefresh();
  if (!refresh_token) return false;

  if (!refreshing) {
    refreshing = (async () => {
      try {
        const res = await fetch(`${API_AUTH}/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token }),
        });
        if (!res.ok) return false;
        setTokens((await res.json()) as TokenPair);
        return true;
      } catch {
        return false;
      } finally {
        refreshing = null;
      }
    })();
  }
  return refreshing;
}

/** Thrown when the session cannot be recovered — callers redirect to /login. */
export class SessionExpired extends Error {
  constructor() {
    super("Session expired");
    this.name = "SessionExpired";
  }
}

interface FetchOptions extends RequestInit {
  /** set false for the auth endpoints that must not attach a bearer */
  auth?: boolean;
}

/**
 * fetch wrapper: attaches the access token, and on a 401 tries a single token
 * refresh + retry. If refresh fails, clears the session and throws
 * SessionExpired so the caller can bounce to the login screen.
 */
export async function apiFetch<T>(path: string, opts: FetchOptions = {}): Promise<T> {
  const { auth = true, headers, ...rest } = opts;

  const build = (): RequestInit => {
    const h = new Headers(headers);
    const token = getAccess();
    if (auth && token) h.set("Authorization", `Bearer ${token}`);
    return { ...rest, headers: h };
  };

  let res = await fetch(path, build());

  if (res.status === 401 && auth) {
    const ok = await refreshTokens();
    if (!ok) {
      clearTokens();
      throw new SessionExpired();
    }
    res = await fetch(path, build());
    if (res.status === 401) {
      clearTokens();
      throw new SessionExpired();
    }
  }

  if (!res.ok) throw await parseError(res);

  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}
