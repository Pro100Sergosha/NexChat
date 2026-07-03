import { refreshTokens } from "./api";
import { getAccess } from "./tokens";
import { WS_CLOSE, type MessageOut, type WSSendMessage } from "./types";

export type LineStatus = "connecting" | "open" | "reconnecting" | "closed";

export interface ChatSocketHandlers {
  onMessage: (msg: MessageOut) => void;
  onStatus: (status: LineStatus) => void;
  /** Non-recoverable auth failure — the session is dead, bounce to login. */
  onAuthFail: () => void;
  /** A rejected frame (4403 not participant, 4422 bad frame). */
  onReject: (code: number) => void;
}

function wsUrl(token: string): string {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${location.host}/ws?token=${encodeURIComponent(token)}`;
}

/**
 * Manages the chat WebSocket lifecycle: connect, send, auto-reconnect with
 * backoff, and the special close-code handling (4401/4403/4422). The socket's
 * status drives the "live line" signature in the UI.
 */
export class ChatSocket {
  private ws: WebSocket | null = null;
  private manualClose = false;
  private retries = 0;
  private authRetried = false;
  private timer: ReturnType<typeof setTimeout> | null = null;

  constructor(private readonly handlers: ChatSocketHandlers) {}

  connect(): void {
    this.manualClose = false;
    const token = getAccess();
    if (!token) {
      this.handlers.onAuthFail();
      return;
    }

    this.handlers.onStatus(this.retries > 0 ? "reconnecting" : "connecting");
    const ws = new WebSocket(wsUrl(token));
    this.ws = ws;

    ws.onopen = () => {
      this.retries = 0;
      this.authRetried = false;
      this.handlers.onStatus("open");
    };

    ws.onmessage = (ev) => {
      try {
        this.handlers.onMessage(JSON.parse(ev.data as string) as MessageOut);
      } catch {
        /* ignore malformed inbound frame */
      }
    };

    ws.onclose = (ev) => {
      this.ws = null;
      if (this.manualClose) {
        this.handlers.onStatus("closed");
        return;
      }
      void this.handleClose(ev.code);
    };

    // onerror is always followed by onclose — reconnect is handled there.
    ws.onerror = () => ws.close();
  }

  private async handleClose(code: number): Promise<void> {
    if (code === WS_CLOSE.AUTH) {
      // Try one token refresh before giving up on the session.
      if (!this.authRetried && (await refreshTokens())) {
        this.authRetried = true;
        this.connect();
        return;
      }
      this.handlers.onStatus("closed");
      this.handlers.onAuthFail();
      return;
    }

    if (code === WS_CLOSE.FORBIDDEN || code === WS_CLOSE.BAD_FRAME) {
      // The frame was rejected but the session is fine; the server closes the
      // socket, so surface the reason and reconnect to keep the line live.
      this.handlers.onReject(code);
    }

    this.scheduleReconnect();
  }

  private scheduleReconnect(): void {
    this.retries += 1;
    const delay = Math.min(500 * 2 ** (this.retries - 1), 8000);
    this.handlers.onStatus("reconnecting");
    this.timer = setTimeout(() => this.connect(), delay);
  }

  send(frame: WSSendMessage): boolean {
    if (this.ws?.readyState !== WebSocket.OPEN) return false;
    this.ws.send(JSON.stringify(frame));
    return true;
  }

  close(): void {
    this.manualClose = true;
    if (this.timer) clearTimeout(this.timer);
    this.ws?.close();
    this.ws = null;
  }
}
