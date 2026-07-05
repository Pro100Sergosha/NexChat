import { refreshTokens } from "./api";
import { eventsUrl } from "./notifications";
import { getAccess } from "./tokens";
import type { NotificationItem } from "./types";

export type StreamStatus = "connecting" | "open" | "reconnecting" | "closed";

export interface NotifStreamHandlers {
  onNotification: (n: NotificationItem) => void;
  onStatus: (status: StreamStatus) => void;
}

/**
 * Owns the notifications SSE connection: connect, relay each pushed frame, and
 * reconnect on drop. EventSource can't surface the HTTP status, so a likely
 * token expiry is handled by refreshing once and reconnecting immediately
 * (mirrors ChatSocket's 4401 path); anything else falls back to backoff.
 */
export class NotifStream {
  private es: EventSource | null = null;
  private manualClose = false;
  private retries = 0;
  private authRetried = false;
  private timer: ReturnType<typeof setTimeout> | null = null;

  constructor(private readonly handlers: NotifStreamHandlers) {}

  connect(): void {
    this.manualClose = false;
    const token = getAccess();
    if (!token) {
      this.handlers.onStatus("closed");
      return;
    }

    this.handlers.onStatus(this.retries > 0 ? "reconnecting" : "connecting");
    const es = new EventSource(eventsUrl(token));
    this.es = es;

    es.onopen = () => {
      this.retries = 0;
      this.authRetried = false;
      this.handlers.onStatus("open");
    };

    es.onmessage = (ev) => {
      try {
        this.handlers.onNotification(JSON.parse(ev.data as string) as NotificationItem);
      } catch {
        /* ignore malformed frame */
      }
    };

    es.onerror = () => {
      // Native EventSource would silently retry with the same stale token; take
      // over so we can refresh first.
      es.close();
      this.es = null;
      if (this.manualClose) return;
      void this.handleError();
    };
  }

  private async handleError(): Promise<void> {
    // First drop: the access token may just have expired — refresh once and
    // reconnect straight away before falling back to backoff.
    if (!this.authRetried && (await refreshTokens())) {
      this.authRetried = true;
      this.connect();
      return;
    }
    this.scheduleReconnect();
  }

  private scheduleReconnect(): void {
    this.retries += 1;
    const delay = Math.min(1000 * 2 ** (this.retries - 1), 30_000);
    this.handlers.onStatus("reconnecting");
    this.timer = setTimeout(() => this.connect(), delay);
  }

  close(): void {
    this.manualClose = true;
    if (this.timer) clearTimeout(this.timer);
    this.es?.close();
    this.es = null;
  }
}
