import { Route, Routes } from "react-router-dom";
import { Chat } from "./pages/chatGPT/chat";
import {
  ChatInterface,
  ConversationSessionResponse,
} from "./interfaces/interfaces";
import { useEffect, useState } from "react";
import { MainLayout } from "./components/layout/MainLayout";
import api from "./api/ApiGPT";
import UseLogout from "./hooks/useLogout";

export default function PrivateRoutes() {
  const [chats, setChats] = useState<ChatInterface[]>([]);
  const [allMessages, setAllMessages] = useState({});
  const { logout, user } = UseLogout();
  const [isLoadingChats, setIsLoadingChats] = useState(false);

  function getAllChats() {
    if (!user) return;
    setIsLoadingChats(true);
    const token = sessionStorage.getItem("accessToken") || "";
    api
      .requestAllSession(token)
      .then((res: ConversationSessionResponse) => {
        // Formatear la data para almacenarlo en la variable chats
        setChats(
          res.sessions.map((chat) => {
            return {
              ...chat,
              chatId: chat.id,
              title: chat.conversation_name,
            };
          })
        );
      })
      .catch((err) => {
        console.log(err);
        logout(err?.status || "");
      })
      .finally(() => setIsLoadingChats(false));
  }

  function removeChatFromState(chatId: string) {
    if (!chatId) return;

    // 1. Eliminar el chat de la lista
    setChats((prev) => prev.filter((chat) => chat.chatId !== chatId));

    // 2. Eliminar los mensajes asociados en allMessages
    setAllMessages((prev: any) => {
      const newObj = { ...prev };
      delete newObj[chatId];
      return newObj;
    });
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
            isLoading={isLoadingChats}
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
