// Wire contracts — mirror the auth and chat backend schemas exactly.

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string; // UUID string — this is the caller's own user id
  email: string;
  username: string;
  email_verified: boolean;
}

// id → display name, resolved via /users/{id} or /users/by-username/{username}.
export interface PublicUser {
  id: string;
  username: string;
}

export interface ConversationOut {
  id: number;
  other_user_id: string;
  created_at: string;
  last_message_at: string | null;
}

export interface MessageOut {
  id: number;
  conversation_id: number;
  sender_id: string;
  content: string;
  created_at: string;
}

// A transcript entry: a persisted message, or an optimistic one awaiting echo.
export interface ChatMessage extends MessageOut {
  pending?: boolean;
}

// client -> server WS frame; at least one of recipient_id / conversation_id
export interface WSSendMessage {
  content: string;
  recipient_id?: string;
  conversation_id?: number;
}

// Every backend error body is { code, message }.
export interface ApiErrorBody {
  code: string;
  message: string;
}

// WebSocket close codes carry the failure reason (no JSON body on the socket).
export const WS_CLOSE = {
  AUTH: 4401, // token invalid or expired
  FORBIDDEN: 4403, // not a participant of the conversation
  BAD_FRAME: 4422, // malformed frame / empty / too long
} as const;
