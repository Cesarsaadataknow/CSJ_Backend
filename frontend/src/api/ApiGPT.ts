import axios, { AxiosInstance } from "axios";
import type {
  ConversationSessionResponse,
  ConversationDetailResponse,
  AskResponse,
  UploadResponse,
  TokenResponse,
} from "@/interfaces/interfaces";

const BASE_URL = `${import.meta.env.VITE_APP_API_URL || "http://localhost:8000"}/api`;

const apiClientMultipart: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: {
    "Content-Type": "multipart/form-data",
  },
});

const apiClientCommon: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

/* 🔐 Interceptor global igual al de Vue */
apiClientCommon.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail;

    if (
      (status === 401 || status === 403) &&
      (detail === "Token inválido" ||
        detail === "Token expirado" ||
        detail === "Not authenticated" ||
        detail === "Claims inválidos")
    ) {
      localStorage.removeItem("access_token");
      window.location.href = `${BASE_URL}/auth/login`;
    }

    return Promise.reject(error);
  },
);

// Tipos
interface ChatRequestData {
  question: string;
  session_id?: string;
}

interface VoteRequestData {
  id: string;
  thread_id: string;
  rate: number;
}

interface ApiResponse<T> {
  data: T;
}

const api = {
  async requestToken(code: string): Promise<TokenResponse> {
    const response = await apiClientCommon.get<TokenResponse>(`/auth/token?code=${code}`);
    return response.data;
  },

  async requestLogin(): Promise<void> {
    window.location.href = `${BASE_URL}/auth/login`;
  },

  async requestAllSession(token: string): Promise<ConversationSessionResponse> {
    const response: ApiResponse<ConversationSessionResponse> = await apiClientCommon.get("/sessions", {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    return response.data;
  },

  async requestOneSession(conversation_id: string): Promise<ConversationDetailResponse> {
    const token = localStorage.getItem("access_token");
    const response: ApiResponse<ConversationDetailResponse> = await apiClientCommon.get(
      "/get_one_session",
      {
        params: { conversation_id },
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );
    return response.data;
  },

  async requestDeleteSession(session_id: string): Promise<unknown> {
    const token = localStorage.getItem("access_token");
    const response: ApiResponse<unknown> = await apiClientCommon.delete(
      `/delete_one_session/${session_id}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );
    return response.data;
  },

  async requestChat({
    question,
    session_id,
  }: {
    question: string;
    session_id?: string | null;
  }): Promise<AskResponse> {
    const requestData: ChatRequestData = { question };

    // Solo envía session_id si existe
    if (session_id) {
      requestData.session_id = session_id;
    }

    const token = localStorage.getItem("access_token");
    const response: ApiResponse<AskResponse> = await apiClientCommon.post(
      "/ask",
      requestData,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );
    return response.data;
  },
  async requestAttachment(files: File[], sessionId: string): Promise<UploadResponse> {
    const token = localStorage.getItem("access_token");
    const formData = new FormData();

    files.forEach((file) => {
      formData.append("files", file);
    });

    const response: ApiResponse<UploadResponse> = await apiClientMultipart.post(
      `/upload?session_id=${sessionId}`,
      formData,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );
    return response.data;
  },

  async requestVote(
    msg_id: string,
    vote: number,
    session_id: string,
  ): Promise<unknown> {
    const requestData: VoteRequestData = {
      id: msg_id,
      thread_id: session_id,
      rate: vote,
    };

    const token = localStorage.getItem("access_token");
    const response: ApiResponse<unknown> = await apiClientCommon.post(
      "/chat/vote",
      requestData,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );
    return response.data;
  },
};

export default api;
