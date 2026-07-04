import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/auth/AuthContext";
import { useAlerts } from "@/alerts/AlertsContext";
import { useChatSocket } from "@/hooks/useChatSocket";
import { getConversations, getMessages } from "@/core/chat";
import { shortId } from "@/core/format";
import { WS_CLOSE, type ChatMessage, type ConversationOut, type MessageOut } from "@/core/types";
import { TopBar } from "@/components/TopBar/TopBar";
import { LineRail } from "@/components/LineRail/LineRail";
import { LiveLine } from "@/components/LiveLine/LiveLine";
import { Transcript } from "@/components/Transcript/Transcript";
import { Composer } from "@/components/Composer/Composer";
import styles from "./Chat.module.css";

const REJECT_MESSAGE: Record<number, string> = {
  [WS_CLOSE.FORBIDDEN]: "You're not a participant of that line.",
  [WS_CLOSE.BAD_FRAME]: "Message rejected — empty, too long, or that id can't be reached.",
};

export function ChatPage() {
  const { user, signOut } = useAuth();
  const alerts = useAlerts();

  const [conversations, setConversations] = useState<ConversationOut[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [draftRecipient, setDraftRecipient] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [unread, setUnread] = useState<Record<number, number>>({});
  const [notice, setNotice] = useState<string | null>(null);
  const [pulseKey, setPulseKey] = useState(0);
  const [mobileLine, setMobileLine] = useState(false);

  // Refs so the socket's long-lived handlers see current selection.
  const activeIdRef = useRef<number | null>(null);
  const draftRef = useRef<string | null>(null);
  const convRef = useRef<ConversationOut[]>([]);
  const tempId = useRef(-1);
  const meId = user?.id ?? "";

  useEffect(() => {
    activeIdRef.current = activeId;
  }, [activeId]);
  useEffect(() => {
    draftRef.current = draftRecipient;
  }, [draftRecipient]);
  useEffect(() => {
    convRef.current = conversations;
  }, [conversations]);

  const refreshConversations = useCallback(async () => {
    setConversations(await getConversations());
  }, []);

  // Load an existing conversation's transcript.
  const selectConversation = useCallback(async (id: number) => {
    activeIdRef.current = id;
    setActiveId(id);
    setDraftRecipient(null);
    draftRef.current = null;
    setNotice(null);
    setMobileLine(true);
    setMessages([]);
    // Opening a line clears its unread tally.
    setUnread((u) => {
      if (!u[id]) return u;
      const next = { ...u };
      delete next[id];
      return next;
    });
    try {
      const msgs = await getMessages(id);
      if (activeIdRef.current === id) setMessages(msgs);
    } catch {
      setNotice("Couldn't load that line's history.");
    }
  }, []);

  // Dispatch an inbound frame (delivery to recipient, or echo to sender).
  const onMessage = useCallback(
    (msg: MessageOut) => {
      if (msg.conversation_id === activeIdRef.current) {
        setMessages((prev) => reconcile(prev, msg));
      }

      // Incoming from the other party: track unread + raise an alert unless
      // it's the line we're actively looking at in a focused tab.
      if (msg.sender_id !== meId) {
        const active = activeIdRef.current;
        if (msg.conversation_id !== active) {
          setUnread((u) => ({
            ...u,
            [msg.conversation_id]: (u[msg.conversation_id] ?? 0) + 1,
          }));
        }
        if (msg.conversation_id !== active || document.hidden) {
          const other =
            convRef.current.find((c) => c.id === msg.conversation_id)
              ?.other_user_id ?? msg.sender_id;
          alerts.fire({
            title: `New message · ${shortId(other)}`,
            body: msg.content,
            desktop: document.hidden,
          });
        }
      }

      const known = convRef.current.some((c) => c.id === msg.conversation_id);
      if (known) {
        setConversations((prev) => bump(prev, msg));
      } else {
        // A brand-new line was created (usually our own first message).
        void (async () => {
          await refreshConversations();
          if (msg.sender_id === meId && draftRef.current) {
            void selectConversation(msg.conversation_id);
          }
        })();
      }
    },
    [meId, alerts, refreshConversations, selectConversation],
  );

  const onAuthFail = useCallback(() => {
    void signOut();
  }, [signOut]);

  const onReject = useCallback((code: number) => {
    setNotice(REJECT_MESSAGE[code] ?? "Message rejected.");
  }, []);

  const { status, send } = useChatSocket({ onMessage, onAuthFail, onReject });

  useEffect(() => {
    void refreshConversations();
  }, [refreshConversations]);

  // Reflect the total unread count in the tab title.
  useEffect(() => {
    const total = Object.values(unread).reduce((a, b) => a + b, 0);
    document.title = total > 0 ? `(${total}) NexChat` : "NexChat";
    return () => {
      document.title = "NexChat";
    };
  }, [unread]);

  function openNewLine(recipientId: string) {
    if (recipientId === meId) {
      setNotice("That's your own id — pick someone else's.");
      return;
    }
    setDraftRecipient(recipientId);
    draftRef.current = recipientId;
    setActiveId(null);
    activeIdRef.current = null;
    setMessages([]);
    setNotice(null);
    setMobileLine(true);
  }

  function sendMessage(content: string) {
    let ok = false;
    if (activeId != null) {
      ok = send({ content, conversation_id: activeId });
      if (ok) {
        setMessages((prev) => [
          ...prev,
          {
            id: tempId.current--,
            conversation_id: activeId,
            sender_id: meId,
            content,
            created_at: new Date().toISOString(),
            pending: true,
          },
        ]);
      }
    } else if (draftRecipient) {
      ok = send({ content, recipient_id: draftRecipient });
    }

    if (ok) setPulseKey((k) => k + 1);
    else setNotice("Line isn't connected yet — hold on.");
  }

  if (!user) return null;

  const activeConv = conversations.find((c) => c.id === activeId) ?? null;
  const hasTarget = activeId != null || draftRecipient != null;
  const channelLabel = activeConv
    ? `CH.${String(activeConv.id).padStart(3, "0")}`
    : draftRecipient
      ? "New line"
      : "—";
  const party = activeConv
    ? shortId(activeConv.other_user_id)
    : draftRecipient
      ? shortId(draftRecipient)
      : "no line";
  const emptyHint = draftRecipient
    ? "New line. Send a message to open it."
    : activeId != null
      ? "No messages on this line yet."
      : "Select a line, or open a new one.";

  return (
    <div className={styles.page}>
      <TopBar meId={meId} meEmail={user.email} onLogout={() => void signOut()} />

      <div className={styles.body} data-view={mobileLine ? "line" : "rail"}>
        <LineRail
          conversations={conversations}
          activeId={activeId}
          unread={unread}
          onSelect={(id) => void selectConversation(id)}
          onNewLine={openNewLine}
        />

        <section className={styles.line}>
        <div className={styles.lineTop}>
          <button
            className={styles.back}
            onClick={() => setMobileLine(false)}
            type="button"
          >
            ‹ Lines
          </button>
          <div className={styles.lineHeadWrap}>
            <LiveLine
              status={status}
              channelLabel={channelLabel}
              party={party}
              pulseKey={pulseKey}
            />
          </div>
        </div>

        <Transcript messages={messages} meId={meId} emptyHint={emptyHint} />

        {notice && (
          <p className={styles.notice} role="status">
            <span aria-hidden>›</span> {notice}
          </p>
        )}

        <Composer
          disabled={!hasTarget || status !== "open"}
          hint="type on the line…"
          onSend={sendMessage}
        />
        </section>
      </div>
    </div>
  );
}

function reconcile(prev: ChatMessage[], msg: MessageOut): ChatMessage[] {
  const pi = prev.findIndex(
    (m) => m.pending && m.sender_id === msg.sender_id && m.content === msg.content,
  );
  if (pi >= 0) {
    const copy = [...prev];
    copy[pi] = msg;
    return copy;
  }
  if (prev.some((m) => m.id === msg.id)) return prev;
  return [...prev, msg];
}

function bump(prev: ConversationOut[], msg: MessageOut): ConversationOut[] {
  const idx = prev.findIndex((c) => c.id === msg.conversation_id);
  if (idx < 0) return prev;
  const updated = { ...prev[idx]!, last_message_at: msg.created_at };
  return [updated, ...prev.filter((_, i) => i !== idx)];
}
