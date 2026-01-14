/* eslint-disable @typescript-eslint/no-explicit-any */
import { useScrollToBottom } from "@/components/custom/use-scroll-to-bottom";
import {
  useState,
  useEffect,
  Dispatch,
  SetStateAction,
  useRef,
  Fragment,
} from "react";
import { v4 as uuidv4 } from "uuid";
import { useNavigate, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { Copy, Pencil, X, Check, RefreshCwIcon } from "lucide-react";
import { toast } from "sonner";
import { ThumbDownIcon, ThumbUpIcon } from "@/components/custom/icons";
import { InputGPT } from "@/components/gpt/InputGPT";
import api from "@/api/ApiGPT";
import {
  ChatInterface,
  ConversationDetailResponse,
  ConversationMessage,
} from "@/interfaces/interfaces";
import ListFile from "@/components/custom/ListFile";
import { Button } from "@/components/ui/button";
import UseLogout from "@/hooks/useLogout";

interface Message {
  id: string;
  role: "user" | "assistant";
  answer: string;
  files: File[] | string[] | null;
  rate: null | number;
  linkFile: string;
}

type props = {
  newChat?: boolean;
  setChats: Dispatch<SetStateAction<ChatInterface[]>>;
  chats: ChatInterface[];
  allMsgs: Record<string, Message[]>;
  setAllMsg: Dispatch<SetStateAction<Record<string, Message[]>>>;
};

export function Chat({
  newChat = false,
  setChats,
  chats,
  allMsgs,
  setAllMsg,
}: props) {
  const [messagesContainerRef, messagesEndRef] =
    useScrollToBottom<HTMLDivElement>();
  const [question, setQuestion] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [idChat, setIdChat] = useState<string>("");
  const [instructions, setInstructions] = useState("");
  const [isLoadingChat, setIsLoadingChat] = useState<boolean>(false);
  const { id } = useParams<{ id?: string }>();
  const navigate = useNavigate();
  const isStop = useRef<boolean>(false);
  const { logout, user } = UseLogout();

  const pushMessage = (msg: Message, idChatValue: string | null = null) => {
    setAllMsg((prev: any) => ({
      ...prev,
      [idChatValue || idChat]: [...(prev[idChatValue || idChat] || []), msg],
    }));
  };

  const updateMessageText = (messageId: string, text: string) => {
    const allMsgCopy = {
      ...allMsgs,
      [idChat]: allMsgs[idChat].map((m: Message) =>
        m.id === messageId && m.role == "user" ? { ...m, answer: text } : m
      ),
    };
    setAllMsg(allMsgCopy);
    handleEdit(messageId, allMsgCopy);
  };

  const formatText = (answer: any) => {
    if (typeof answer == "object") {
      return Object.values(answer).filter(Boolean).join("\n\n\n\n");
    }
    return answer;
  };

  const handleSubmit = async ({
    text = "",
    idMessageCorrected = "",
    is_regenerate = false,
    files,
  }: {
    text: string;
    idMessageCorrected?: string;
    is_regenerate: boolean;
    files: File[] | null;
  }) => {
    if (isLoading) return;
    const messageId = idMessageCorrected || uuidv4();
    const DESIRED_LENGTH = 28;
    const messageText = text;
    const isChat = chats.findIndex((chat) => chat.chatId == idChat);
    const idChatLocal = idChat;

    const titleChat =
      isChat >= 0
        ? chats[isChat].title
        : messageText.length > DESIRED_LENGTH
        ? messageText.substring(0, DESIRED_LENGTH)
        : messageText;

    // Crear nueva sesión si no existe
    // if (isChat < 0) {
    //   try {
    //     const res: any = await api.create_session(
    //       user1?.userName || "",
    //       titleChat
    //     );
    //     idChatLocal = res.session_id;
    //     setIdChat(idChatLocal);
    //   } catch (err: any) {
    //     logout(err?.status || "");
    //     return;
    //   }
    // }

    if (!is_regenerate) {
      pushMessage(
        {
          id: messageId,
          answer: text,
          role: "user",
          files,
          rate: null,
          linkFile: "",
        },
        idChatLocal
      );
    }

    setIsLoading(true);
    try {
      let assistantText = "";
      let linkFile = "";
      if (files?.length) {
        const formData = new FormData();
        formData.append("user_id", "user@test.com");
        formData.append("session_id", idChatLocal);
        formData.append("question", messageText);
        // formData.append("flag_modifier", String(is_regenerate));
        // formData.append("model_name", modelSelect.toLowerCase());
        // formData.append("search_tool", String(isSearch));

        files.forEach((fileObj: any) => {
          formData.append("files", fileObj);
        });

        const res = await api.requestAttachment(formData);
        assistantText = formatText(res.answer);
        linkFile = res.file;
      } else {
        const res = await api.requestChat({
          question: text,
          session_id: idChatLocal,
          user_id: "user@test.com",
        });
        assistantText = formatText(res.answer);
        linkFile = res.file;
      }

      if (isStop.current) {
        isStop.current = false;
        return;
      }

      pushMessage(
        {
          id: messageId,
          answer: assistantText,
          role: "assistant",
          files: [],
          rate: null,
          linkFile,
        },
        idChatLocal
      );
    } catch (error: any) {
      logout(error?.response?.statusText || "");
      pushMessage(
        {
          id: messageId,
          answer: "Hubo un error al procesar tu mensaje.",
          role: "assistant",
          files: [],
          rate: null,
          linkFile: "",
        },
        idChatLocal
      );
    } finally {
      if (newChat) {
        setChats((prev) => [
          {
            chatId: idChatLocal,
            title: titleChat,
            created_at: JSON.stringify(new Date()),
          },
          ...prev,
        ]);
        navigate(`c/${idChatLocal}`);
      }
      setIsLoading(false);
      setFiles([]);
    }
  };

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast?.success("Copiado al portapapeles");
    } catch {
      toast?.error("No se pudo copiar el texto");
    }
  };

  const startEditing = (msg: Message) => {
    setEditingId(msg.id);
    setEditText(msg.answer);
  };

  const cancelEditing = () => {
    setEditingId(null);
    setEditText("");
  };

  const saveEdit = () => {
    if (!editingId) return;
    updateMessageText(editingId, editText);
    toast.success("Mensaje actualizado");
    setEditingId(null);
  };

  const getMessages = (id: string) => {
    if (allMsgs[id]) return;
    setIsLoadingChat(true);
    api
      .requestOneSession(id)
      .then((res: ConversationDetailResponse) => {
        const msgs: ConversationMessage[] = res.messages ?? [];
        if (msgs.length == 0) {
          toast.error(`No existe la conversación ${id}`);
          navigate("/");
          return;
        }
        setAllMsg((prev) => {
          return {
            ...prev,
            [id]: (msgs ?? []).map((msg) => {
              return {
                answer: msg.content,
                files: msg.files,
                id: msg.id,
                role: msg.role,
                rate: msg?.rate || null,
                linkFile: msg?.file || "",
              };
            }),
          };
        });
        // eslint-disable-next-line @typescript-eslint/no-unused-expressions
        res.messages.map;
      })
      .catch((err: any) => {
        toast.error(`No existe la conversación ${id}`);
        navigate("/");

        logout(err?.status || "");
      })
      .finally(() => setIsLoadingChat(false));
  };

  const handleRegenerate = (id: string) => {
    const messages = allMsgs[idChat] ?? [];
    const index = messages.findIndex(
      (msg) => msg.id == id && msg.role == "assistant"
    );
    const userMsg = messages[index - 1];
    // Eliminar los mensajes desde la posición donde se seleccionó
    removeFromSpecificToEnd(index);
    // Re-enviar el mismo mensaje del usuario
    handleSubmit({
      text: userMsg.answer,
      idMessageCorrected: userMsg.id,
      is_regenerate: true,
      files: null,
    });
    return;
  };

  const handleEdit = (id: string, data: Record<string, Message[]>) => {
    const messages = [...(data[idChat] ?? [])];
    const index = messages.findIndex(
      (msg) => msg.id == id && msg.role == "user"
    );

    const userMsg = messages[index];
    // Eliminar los mensajes desde la posición donde se seleccionó
    removeFromSpecificToEnd(index + 1);
    // Re-enviar el mismo mensaje del usuario
    handleSubmit({
      text: userMsg.answer,
      idMessageCorrected: userMsg.id,
      is_regenerate: true,
      files: null,
    });
    return;
  };

  const removeFromSpecificToEnd = (i: number) => {
    setAllMsg((prev) => ({
      ...prev,
      [idChat]: prev[idChat].slice(0, i),
    }));
  };

  useEffect(() => {
    setIdChat(id || uuidv4());
    if (id) {
      getMessages(id);
    }
  }, [id]);

  const handleStop = async () => {
    isStop.current = true;
    setIsLoading(false);
    pushMessage({
      id: uuidv4(),
      answer: "El mesaje fue cancelado por el usuario",
      role: "assistant",
      files: null,
      rate: null,
      linkFile: "",
    });
    //   try {
    //   await api.requestVote(stop_msg_id, 2);
    // } catch (error) {
    //   toast.error("Error al detener la conversación")
    // }
  };

  const handleVote = async (
    vote: number,
    value: number | null,
    idMessage: string,
    idChat: string
  ) => {
    if (!user) return;
    if (value === null) {
      // Cambiar valor de rate
      setAllMsg((prev) => {
        return {
          ...prev,
          [idChat]: prev[idChat].map((msg) =>
            msg.id == idMessage ? { ...msg, rate: vote } : msg
          ),
        };
      });
      try {
        await api.requestVote(idMessage, vote, idChat);
      } catch (err: any) {
        logout(err?.response?.statusText || "");
      }
    }
  };

  const endRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [allMsgs?.[idChat], isLoadingChat]);
  return (
    <>
      <div
        className="flex flex-col w-full max-w-4xl gap-6 flex-1 overflow-y-auto pt-4 scrollbar-thin px-2 scrollbar-thumb-gray-400 scrollbar-track-gray-100"
        ref={messagesContainerRef}
      >
        <div className="flex-1 text-sm space-y-2 flex flex-col">
          {isLoadingChat && <ChatSkeleton />}
          {newChat && (
            <div className="flex flex-1 justify-center items-center p-2">
              <h1 className="text-3xl font-bold break-all text-center">
                ¡Hola, <span className="font-normal">{"Test"}</span>!
              </h1>
            </div>
          )}
          {!isLoadingChat &&
            (allMsgs[idChat] ?? []).map((msg, i) => (
              <Fragment key={i}>
                {msg.role === "user" && (
                  <div className="flex flex-col group gap-2 items-end">
                    <ListFile files={msg.files} />
                    {msg.answer && (
                      <div
                        className={`bg-gray-100 px-4 py-2 rounded-lg border border-gray-300 shadow-sm w-fit max-w-xl ${
                          editingId == msg.id && "!w-full"
                        }`}
                      >
                        {editingId === msg.id ? (
                          <textarea
                            value={editText}
                            onChange={(e) => setEditText(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Escape") cancelEditing();
                            }}
                            className="bg-transparent outline-none border-b border-gray-400 text-left w-full"
                            rows={4}
                            autoFocus
                          />
                        ) : (
                          <p>{msg.answer}</p>
                        )}
                      </div>
                    )}

                    <div
                      className={`flex flex-row gap-2  ${
                        editingId === msg.id
                          ? ""
                          : "opacity-100 lg:opacity-0 lg:group-hover:opacity-100"
                      }`}
                    >
                      {editingId === msg.id && !msg.files?.length ? (
                        <>
                          <Button
                            variant={"outline"}
                            className="w-fit h-fit p-2 rounded-full"
                            onClick={saveEdit}
                          >
                            <Check size={16} />
                          </Button>
                          <Button
                            variant={"outline"}
                            className="w-fit h-fit p-2 rounded-full"
                            onClick={cancelEditing}
                          >
                            <X size={16} />
                          </Button>
                        </>
                      ) : (
                        <>
                          <Button
                            variant="outline"
                            className="w-fit h-fit p-2 rounded-full"
                            onClick={() => handleCopy(msg.answer)}
                          >
                            <Copy size={16} />
                          </Button>
                          <Button
                            variant="outline"
                            className="w-fit h-fit p-2 rounded-full"
                            onClick={() => startEditing(msg)}
                          >
                            <Pencil size={16} />
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                )}

                {msg.role === "assistant" && (
                  <div>
                    <div className="text-neutral-700 w-fit max-w-8/12 rounded-2xl rounded-tr-none p-2 ia-response prose">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        rehypePlugins={[rehypeRaw]}
                        components={{
                          code: ({ children, node }) => {
                            const isBlock =
                              node?.position?.start && node?.position?.end
                                ? node?.tagName === "pre"
                                : false;

                            if (isBlock) {
                              // BLOQUE DE CÓDIGO: <pre><code>...</code></pre>
                              return (
                                <code className="text-white">{children}</code>
                              );
                            }

                            // INLINE CODE (no tocar)
                            return <code>{children}</code>;
                          },
                        }}
                      >
                        {msg.answer}
                      </ReactMarkdown>
                      {msg.linkFile ? (
                        <Button onClick={() => console.log(msg.linkFile)}>
                          Descargar .docx
                        </Button>
                      ) : (
                        <></>
                      )}
                    </div>
                    <div className="flex flex-row">
                      <Button
                        variant="outline"
                        className="p-2 rounded-full border-none w-fit h-fit"
                        onClick={() => handleCopy(msg.answer)}
                      >
                        <Copy size={16} />
                      </Button>
                      <Button
                        variant={msg.rate === 1 ? "active" : "outline"}
                        className="p-2 rounded-full border-none w-fit h-fit"
                        disabled={msg.rate !== null}
                        onClick={() => handleVote(1, msg.rate, msg.id, idChat)}
                      >
                        <ThumbUpIcon size={16} />
                      </Button>
                      <Button
                        variant={msg.rate === 0 ? "active" : "outline"}
                        className="p-2 rounded-full border-none w-fit h-fit"
                        disabled={msg.rate !== null}
                        onClick={() => handleVote(0, msg.rate, msg.id, idChat)}
                      >
                        <ThumbDownIcon size={16} />
                      </Button>
                      <Button
                        variant="outline"
                        className="p-2 rounded-full border-none w-fit h-fit"
                        onClick={() => handleRegenerate(msg.id)}
                      >
                        <RefreshCwIcon size={16} />
                      </Button>
                    </div>
                  </div>
                )}
              </Fragment>
            ))}
          {isLoading && (
            <div className="text-center text-gray-500 italic">
              ⏳ Pensando...
            </div>
          )}
          <div ref={endRef} />
        </div>

        <div
          ref={messagesEndRef}
          className="shrink-0 min-w-[24px] min-h-[24px]"
        />
      </div>

      <InputGPT
        question={question}
        setQuestion={setQuestion}
        onSubmit={handleSubmit}
        isLoading={isLoading}
        instructions={instructions}
        setInstructions={setInstructions}
        hasStartedChat={false}
        key={id}
        files={files}
        setFiles={setFiles}
        handleStop={handleStop}
      />
    </>
  );
}

const ChatSkeleton = () => (
  <div className="p-4 space-y-6">
    {" "}
    {/* Espacio entre los mensajes simulados */}
    {/* Mensaje 1: IA (Izquierda) */}
    <div className="flex justify-start animate-pulse">
      <div
        className="w-full max-w-xl h-8 rounded-xl
                   bg-gray-300 "
      />
    </div>
    {/* Mensaje 2: IA (Izquierda, más corto) */}
    <div className="flex justify-start animate-pulse">
      <div
        className="w-3/4 max-w-md h-8 rounded-xl
                   bg-gray-300 "
      />
    </div>
    {/* Mensaje 3: Usuario (Derecha) */}
    <div className="flex justify-end animate-pulse">
      <div
        className="w-1/3 max-w-xs h-8 rounded-xl
                   /* Usamos un color distintivo para simular el mensaje del usuario */
                   bg-blue-200 dark:bg-gray-800"
      />
    </div>
    {/* Mensaje 4: IA (Izquierda) */}
    <div className="flex justify-start animate-pulse">
      <div
        className="w-4/5 max-w-lg h-8 rounded-xl
                   bg-gray-300 "
      />
    </div>
    {/* Mensaje 5: Usuario (Derecha, más largo) */}
    <div className="flex justify-end animate-pulse">
      <div
        className="w-2/5 max-w-sm h-8 rounded-xl
                   bg-blue-200 dark:bg-gray-800"
      />
    </div>
  </div>
);
