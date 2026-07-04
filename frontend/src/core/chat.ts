import { API_CHAT, apiFetch } from "./api";
import type { ConversationOut, MessageOut } from "./types";

export function getConversations(): Promise<ConversationOut[]> {
  return apiFetch<ConversationOut[]>(`${API_CHAT}/conversations`);
}

export function getMessages(
  conversationId: number,
  limit = 50,
  offset = 0,
): Promise<MessageOut[]> {
  const q = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return apiFetch<MessageOut[]>(`${API_CHAT}/messages/${conversationId}?${q}`);
}
