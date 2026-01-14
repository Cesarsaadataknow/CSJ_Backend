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
    conversation_name: string;
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
}

export interface ConversationDetailResponse {
  conversation_id: string;
  conversation_name: string;
  messages: ConversationMessage[];
}

export interface User {
  name: string;
  email: string;
  roles: ["Tester"];
}
