import { useCallback, useEffect, useRef, useState } from "react";
import { ChatSocket, type LineStatus } from "@/core/ws";
import type { MessageOut, WSSendMessage } from "@/core/types";

interface Opts {
  onMessage: (msg: MessageOut) => void;
  onAuthFail: () => void;
  onReject: (code: number) => void;
}

/**
 * Owns a single ChatSocket for the component's lifetime. Handlers are read
 * through a ref so the socket is created once but always calls the latest
 * closures (avoids stale activeId etc.).
 */
export function useChatSocket(opts: Opts): {
  status: LineStatus;
  send: (frame: WSSendMessage) => boolean;
} {
  const [status, setStatus] = useState<LineStatus>("connecting");
  const optsRef = useRef(opts);
  optsRef.current = opts;
  const sockRef = useRef<ChatSocket | null>(null);

  useEffect(() => {
    const sock = new ChatSocket({
      onMessage: (m) => optsRef.current.onMessage(m),
      onStatus: setStatus,
      onAuthFail: () => optsRef.current.onAuthFail(),
      onReject: (c) => optsRef.current.onReject(c),
    });
    sockRef.current = sock;
    sock.connect();
    return () => {
      sock.close();
      sockRef.current = null;
    };
  }, []);

  const send = useCallback(
    (frame: WSSendMessage) => sockRef.current?.send(frame) ?? false,
    [],
  );

  return { status, send };
}
