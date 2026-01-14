import axios from "axios";

const api = axios.create({
  baseURL: `${import.meta.env.VITE_APP_API_URL_SQL}/api`, // Asegúrate que coincide con tu backend
  headers: {
    "Content-Type": "application/json",
  },
});


interface RecoverChatRequest {
  user_id: string;
  jwt: string;
}

interface ChatMessage {
  id: string;
  role: "user" | "agent";
  timestamp: string;
  content?: string;
  instructions?: string;
  corrected_sql_query?: string;
  sql_query?: string;
  sql_result?: {
    columns: string[];
    rows: Record<string, string>[];
  };
  final_answer?: string;
}

interface RecoverChatResponse {
  id: string;
  session_id: string;
  user_id: string;
  messages: ChatMessage[];
}

export const recoverChat = async (payload: RecoverChatRequest, token: string): Promise<RecoverChatResponse> => {
  try {
    const response = await api.post(
      "/recover-chat",
      payload,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
      
    );
    return response.data;
  } catch (error) {
    throw error;
  }
};
