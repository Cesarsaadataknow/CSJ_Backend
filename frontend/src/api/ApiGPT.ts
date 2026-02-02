/* eslint-disable @typescript-eslint/no-explicit-any */
import axios, { AxiosInstance } from "axios";

const BASE_URL =
  "https://capp-resolucion-conflictos-compe.whitesand-8bead175.eastus2.azurecontainerapps.io/api";

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

interface ApiResponse<T = any> {
  data: T;
}

const api = {
  async requestToken(code: string): Promise<any> {
    const response: ApiResponse = await apiClientCommon.get(
      `/auth/token?code=${code}`,
    );
    return response.data;
  },

  async requestLogin(): Promise<void> {
    window.location.href = `${BASE_URL}/auth/login`;
  },

  async requestAllSession(token: string): Promise<any> {
    const response: ApiResponse = await apiClientCommon.get("/chat/sessions", {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    return response.data;
  },

  async requestOneSession(conversation_id: string): Promise<any> {
    const token = localStorage.getItem("access_token");
    const response: ApiResponse = await apiClientCommon.get(
      "/chat/get_one_session",
      {
        params: { conversation_id },
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );
    return response.data;
  },

  async requestDeleteSession(session_id: string): Promise<any> {
    const token = localStorage.getItem("access_token");
    const response: ApiResponse = await apiClientCommon.delete(
      `/chat/delete_one_session/${session_id}`,
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
  }): Promise<any> {
    const requestData: ChatRequestData = { question };

    // Solo envía session_id si existe
    if (session_id) {
      requestData.session_id = session_id;
    }

    const token = localStorage.getItem("access_token");
    const response: ApiResponse = await apiClientCommon.post(
      "/chat/json",
      requestData,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );
    return response.data;
  }
,

  async requestAttachment(attachment: any): Promise<any> {
    const token = localStorage.getItem("access_token");
    const response: ApiResponse = await apiClientMultipart.post(
      "/chat/upload",
      attachment,
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
  ): Promise<any> {
    const requestData: VoteRequestData = {
      id: msg_id,
      thread_id: session_id,
      rate: vote,
    };

    const token = localStorage.getItem("access_token");
    const response: ApiResponse = await apiClientCommon.post(
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
