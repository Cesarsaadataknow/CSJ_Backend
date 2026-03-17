import { Route, Routes } from "react-router-dom";
import { Chat } from "./pages/chatGPT/chat";
import {
  ChatInterface,
  ConversationSessionResponse,
} from "./interfaces/interfaces";
import type { Message } from "./pages/chatGPT/chat";
import { useEffect, useState } from "react";
import { MainLayout } from "./components/layout/MainLayout";
import api from "./api/ApiGPT";
import UseLogout from "./hooks/useLogout";

export default function PrivateRoutes() {
  const [chats, setChats] = useState<ChatInterface[]>([]);
  const [allMessages, setAllMessages] = useState<Record<string, Message[]>>({});
  const { logout, user } = UseLogout();
  const [isLoadingChats, setIsLoadingChats] = useState(false);

  function getAllChats() {
    // if (!user) return;
    setIsLoadingChats(true);
    const token = localStorage.getItem("access_token") || "";
    api
      .requestAllSession(token)
      .then((res: ConversationSessionResponse) => {
        // Formatear la data para almacenarlo en la variable chats
        setChats(
          res.sessions.map((chat) => {
            return {
              ...chat,
              chatId: chat.id,
              title: chat.name_session,
            };
          })
        );
      })
      .catch((err: { status?: string; response?: { status?: number } }) => {
        console.log(err);
        const status = err?.response?.status ?? err?.status;
        logout(typeof status === "number" ? String(status) : status ?? "");
      })
      .finally(() => setIsLoadingChats(false));
  }

  function removeChatFromState(chatId: string) {
    if (!chatId) return;

    // 1. Eliminar el chat de la lista
    setChats((prev) => prev.filter((chat) => chat.chatId !== chatId));

    // 2. Eliminar los mensajes asociados en allMessages
    setAllMessages((prev) => {
      const { [chatId]: _removed, ...rest } = prev;
      return rest;
    });
  }

  function renameChatInState(chatId: string, newTitle: string) {
    if (!chatId || !newTitle.trim()) return;
    setChats((prev) =>
      prev.map((chat) =>
        chat.chatId === chatId ? { ...chat, title: newTitle.trim() } : chat
      )
    );
  }

  useEffect(() => {
    getAllChats();
  }, [user]);

  return (
    <Routes>
      {/* Rutas dentro del layout */}
        <Route
          element={
            <MainLayout
              chats={chats}
              removeChatFromState={removeChatFromState}
              renameChatInState={renameChatInState}
              isLoading={isLoadingChats}
              onRefreshChats={getAllChats}
            />
          }
        >
        <Route
          path="/"
          element={
            <Chat
              newChat
              setChats={setChats}
              chats={chats}
              allMsgs={allMessages}
              setAllMsg={setAllMessages}
            />
          }
        />
        <Route
          path="/c/:id"
          element={
            <Chat
              setChats={setChats}
              chats={chats}
              allMsgs={allMessages}
              setAllMsg={setAllMessages}
            />
          }
        />
      </Route>
    </Routes>
  );
}
