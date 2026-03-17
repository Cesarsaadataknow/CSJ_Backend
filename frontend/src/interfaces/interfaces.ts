export interface message {
  content: string;
  role: string;
  id: string;
}

export interface AssistantMessage {
  id: string;
  answer: string;
  table: { [key: string]: string }[];
  columns: string[];
  sql: string;
}

export type Message = {
  id: string;
  role: "user" | "assistant";
  answer: string;
  files: File[];
};
export type ChatInterface = {
  chatId: string;
  title: string;
  created_at: string;
};

export interface ConversationSessionResponse {
  sessions: {
    id: string;
    name_session: string;
    created_at: string;
  }[];
}

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string; // ISO8601
  rate: number | null;
  files: string[] | null;
  file: string;
}

export interface ConversationDetailResponse {
  conversation_id: string;
  conversation_name: string;
  messages: ConversationMessage[];
}

/**
 * Respuesta del endpoint POST /api/ask.
 * Los tipos pueden ajustarse cuando el backend esté documentado.
 */
export interface AskResponse {
  answer: string | Record<string, unknown>;
  doc_id?: string;
  session_id?: string;
}

/**
 * Respuesta del endpoint POST /api/upload.
 * Los tipos pueden ajustarse cuando el backend esté documentado.
 */
export interface UploadResponse {
  reply_text: string | Record<string, unknown>;
  doc_id?: string;
  session_id?: string;
}

export interface User {
  name: string;
  email: string;
  roles: ["Tester"];
}

/**
 * Respuesta del endpoint GET /api/auth/token.
 * Ajustar cuando el backend esté documentado.
 */
export interface TokenResponse {
  access_token?: string;
  permissions?: string;
}
