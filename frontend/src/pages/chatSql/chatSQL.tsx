import { CATALOG, ChatInput } from "@/components/custom/chatinput";
import { useScrollToBottom } from "@/components/custom/use-scroll-to-bottom";
import { useState } from "react";
import { Overview } from "@/components/custom/overview";
import { v4 as uuidv4 } from "uuid";
import Editor from "react-simple-code-editor";
import { useTheme } from "@/context/ThemeContext";
import { highlight, languages } from "prismjs";
import "prismjs/components/prism-sql";
import "prismjs/components/prism-sql";
import "prismjs/themes/prism.css";
import { EChartsWrapper } from "@/components/custom/EchartsWrapper";
import ReactMarkdown from "react-markdown";
import {
  Download,
  FilePenLine,
  Save,
  TableProperties,
  BarChart3,
  Play,
} from "lucide-react";

import { useEffect } from "react";
import { recoverChat } from "@/api/ApiSQL";
import UseLogout from "@/hooks/useLogout";

interface AssistantMessage {
  id: string;
  answer: string;
  table: { [key: string]: string }[];
  columns: string[];
  sql: string;
}

const formatSQL = (sql: string): string => {
  return sql
    .replace(
      /(SELECT|FROM|JOIN|WHERE|GROUP BY|ORDER BY|HAVING|LIMIT)/gi,
      "\n$1"
    )
    .replace(/,/g, ",\n")
    .trim();
};

const printTable = (msg: AssistantMessage) => {
  const { columns, table } = msg;

  if (!columns || !Array.isArray(columns) || !table || !Array.isArray(table)) {
    console.error("Datos inválidos para imprimir la tabla.");
    return;
  }

  const htmlTable = `
    <table border="1" style="border-collapse: collapse; width: 100%; font-family: sans-serif;">
      <thead>
        <tr>${columns.map((col) => `<th>${col}</th>`).join("")}</tr>
      </thead>
      <tbody>
        ${table
          .map(
            (row) => `
          <tr>${columns
            .map((col) => `<td>${row[col] || ""}</td>`)
            .join("")}</tr>
        `
          )
          .join("")}
      </tbody>
    </table>
  `;

  const newWin = window.open("", "Print-Window");
  if (newWin) {
    newWin.document.open();
    newWin.document.write(`
      <html><head><title>Impresión de tabla</title></head>
      <body onload="window.print()">
        ${htmlTable}
      </body></html>
    `);
    newWin.document.close();
  }
};

const downloadCSV = (msg: AssistantMessage) => {
  const { columns, table } = msg;
  const separator = ";";

  const csvContent = [
    columns.map((col) => `"${col}"`).join(separator),
    ...table.map((row) =>
      columns
        .map((col) => {
          const rawVal = row[col] as any;
          const safeVal =
            rawVal !== null && rawVal !== undefined ? rawVal.toString() : "";
          return `"${safeVal.replace(/"/g, '""')}"`;
        })
        .join(separator)
    ),
  ].join("\n");

  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", "tabla.csv");
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};

export function ChatSQL() {
  const [messagesContainerRef, messagesEndRef] =
    useScrollToBottom<HTMLDivElement>();
  const [question, setQuestion] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [userMessages, setUserMessages] = useState<
    { content: string; id: string }[]
  >([]);
  const [showSQL, setShowSQL] = useState<{ [id: string]: boolean }>({});
  const { isDarkMode } = useTheme();
  const [showChart, setShowChart] = useState<{ [id: string]: boolean }>({});
  const [chartType, setChartType] = useState<{ [id: string]: string }>({});
  // 👇 Nuevo: estado para catálogo y esquema seleccionados
  const [selectedSchema, setSelectedSchema] = useState("");
  const [instructions, setInstructions] = useState<string>("");

  const [hasStartedChat, setHasStartedChat] = useState(false);

  const { logout } = UseLogout();

  const handleSubmit = async (text?: string) => {
    if (isLoading) return;

    if (!selectedSchema) {
      alert("⚠️ Por favor selecciona un esquema antes de enviar la pregunta.");
      return;
    }

    const messageText = text || question;
    const traceId = uuidv4();

    setUserMessages((prev) => [...prev, { content: messageText, id: traceId }]);
    setQuestion("");
    setHasStartedChat(true);

    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "end",
      });
    }, 100);

    setIsLoading(true);

    const token = sessionStorage.getItem("accessToken");

    let res: Response | any = null;

    try {
      const res = await fetch(
        `${import.meta.env.VITE_APP_API_URL_SQL}/api/ask`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            question: messageText,
            catalog: CATALOG, // 👈 Usar el seleccionado
            schema: selectedSchema, // 👈 Usar el seleccionado
            instructions: instructions,
          }),
        }
      );

      if (res.status == 401) {
        logout("Unauthorized");
      }

      if (!res.ok) throw new Error("Error en el backend");
      const data = await res.json();

      const { answer, sql_query, sql_result } = data;
      const { columns, rows } = parseSQLResult(sql_result);

      setMessages((prev) => [
        ...prev,
        {
          id: traceId,
          answer,
          columns,
          table: rows,
          sql: formatSQL(sql_query),
        },
      ]);
    } catch (error: any) {
      console.error("Error al contactar el backend:", error);
      logout(error?.status || "");

      // Agregar un mensaje  de error dinamico
      const isTimeout = error.message.includes("timeout");
      const isServerError = res?.status >= 500;

      const friendlyMessage = isTimeout
        ? "Pensar una respuesta está tomando más tiempo de lo esperado. Por favor, intenta de nuevo un poco más tarde."
        : isServerError
        ? "Estoy teniendo algunos problemas técnicos. Intenta nuevamente en un momento, por favor."
        : "No pude procesar tu mensaje en esta ocasión. Por favor, intenta nuevamente en un rato o modifica tu pregunta. Si el problema persiste, por favor contacta con un administrador.";

      setMessages((prev) => [
        ...prev,
        {
          id: traceId,
          answer: friendlyMessage,
          columns: [],
          table: [],
          sql: "",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const parseSQLResult = (
    sqlResult: any
  ): { columns: string[]; rows: any[] } => {
    try {
      return {
        columns: sqlResult.columns || [],
        rows: sqlResult.rows || [],
      };
    } catch (e) {
      console.error("Error parseando sql_result:", e);
      return { columns: [], rows: [] };
    }
  };

  const renderChart = (msg: AssistantMessage, type: string) => {
    const data = msg.table.map((row) => {
      const newRow: any = { ...row };
      msg.columns.slice(1).forEach((key) => {
        newRow[key] =
          typeof row[key] === "string" || typeof row[key] === "number"
            ? parseFloat(String(row[key]).replace(/[^0-9.-]+/g, "")) || 0
            : 0;
      });
      return newRow;
    });

    if (!data || data.length === 0) return null;

    return (
      <div className="my-4">
        <EChartsWrapper
          key={`${msg.id}-${type}`}
          data={data}
          columns={msg.columns}
          chartType={type}
        />
      </div>
    );
  };

  // useEffect(() => {
  //   const fetchHistory = async () => {
  //     const user_id = "p1_example_auth0|648fd12a7c34aa00125a4b98";
  //     const jwt = "p1_example_auth0|648fd12a7c34aa00125a4b98";

  //     try {
  //       const data = await recoverChat({ user_id, jwt });
  //       console.log("Historial recuperado:", data);

  //       if (!data || !Array.isArray(data.messages)) {
  //         console.warn("⚠️ Datos del historial no válidos:", data);
  //         return;
  //       }

  //       const restoredMessages: AssistantMessage[] = [];
  //       const userMsgs: { id: string; content: string }[] = [];

  //       const msgMap = new Map<string, { user?: any; agent?: any }>();

  //       for (const msg of data.messages) {
  //         const existing = msgMap.get(msg.id) || {};
  //         if (msg.role === "user") {
  //           msgMap.set(msg.id, { ...existing, user: msg });
  //         } else if (msg.role === "agent") {
  //           msgMap.set(msg.id, { ...existing, agent: msg });
  //         }
  //       }

  //       msgMap.forEach(({ user, agent }) => {
  //         if (user && agent) {
  //           userMsgs.push({
  //             id: user.id,
  //             content: user.content || "",
  //           });

  //           restoredMessages.push({
  //             id: user.id,
  //             answer: agent.final_answer || "",
  //             columns: agent.sql_result?.columns || [],
  //             table: agent.sql_result?.rows || [],
  //             sql: formatSQL(agent.sql_query || ""),
  //           });
  //         }
  //       });

  //       setUserMessages(userMsgs);
  //       setMessages(restoredMessages);
  //       setHasStartedChat(userMsgs.length > 0);
  //     } catch (e) {
  //       console.warn("No se pudo recuperar historial");
  //       console.error(e);
  //     }
  //   };

  //   fetchHistory();
  // }, []);

  useEffect(() => {
    const fetchHistory = async () => {
      const user_id = "t0_example_auth0|648fd12a7c34aa00125a4b98";
      const jwt = "t0_example_auth0|648fd12a7c34aa00125a4b98";
      const token = sessionStorage.getItem("accessToken");

      if (!token) {
        console.warn("No token found");
        return;
      }

      try {
        const data = await recoverChat({ user_id, jwt }, token);

        if (!data || !Array.isArray(data.messages)) {
          console.warn("⚠️ Datos del historial no válidos:", data);
          return;
        }

        const restoredMessages: AssistantMessage[] = [];
        const userMsgs: { id: string; content: string }[] = [];

        // 👉 Ordenar mensajes por timestamp para mantener el orden original
        const sorted = [...data.messages].sort(
          (a, b) =>
            new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
        );

        for (let i = 0; i < sorted.length - 1; i++) {
          const current = sorted[i];
          const next = sorted[i + 1];

          if (current.role === "user" && next.role === "agent") {
            const pairId = current.id; // usamos el ID del mensaje del usuario como identificador común

            userMsgs.push({
              id: pairId,
              content: current.content || "",
            });

            restoredMessages.push({
              id: pairId,
              answer: next.final_answer || "",
              columns: next.sql_result?.columns || [],
              table: next.sql_result?.rows || [],
              sql: formatSQL(next.sql_query || ""),
            });

            i++; // saltamos el siguiente porque ya fue emparejado
          }
        }

        setUserMessages(userMsgs);
        setMessages(restoredMessages);
        setHasStartedChat(userMsgs.length > 0);
      } catch (e: any) {
        logout(e?.status || "");
        console.error(e);
      }
    };

    fetchHistory();
  }, []);

  return (
    <>
      <div
        className="flex flex-col w-full max-w-4xl gap-6 flex-1 overflow-y-auto pt-4 px-6 scrollbar-thin scrollbar-thumb-gray-400 scrollbar-track-gray-100 dark:scrollbar-thumb-gray-600 dark:scrollbar-track-zinc-800"
        ref={messagesContainerRef}
      >
        {userMessages.length === 0 && <Overview />}
        {userMessages.map((userMsg) => {
          const assistantMsg = messages.find((m) => m.id === userMsg.id);
          return (
            <div key={userMsg.id} className="space-y-4">
              <div className="bg-gray-100 dark:bg-gray-800 p-4 rounded-lg border border-gray-300 dark:border-gray-600 shadow-sm">
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  🙋‍♂️ Usuario:
                </p>
                <p className="text-base text-gray-900 dark:text-gray-100 whitespace-pre-wrap">
                  {userMsg.content}
                </p>
              </div>

              {assistantMsg && (
                <div className="bg-gray-50 dark:bg-gray-900 p-4 rounded-lg border border-gray-300 dark:border-gray-600 shadow-inner">
                  <p className="text-sm font-medium text-indigo-700 dark:text-indigo-300 mb-2">
                    🤖 Asistente:
                  </p>
                  <ReactMarkdown className="prose dark:prose-invert max-w-none text-gray-800 dark:text-gray-100 mb-4">
                    {assistantMsg.answer}
                  </ReactMarkdown>
                  {assistantMsg.table.length > 0 && (
                    <div className="overflow-x-auto mb-4">
                      <table
                        id={`table-${assistantMsg.id}`}
                        className="min-w-full text-sm border border-collapse border-gray-300 bg-white rounded shadow-sm"
                      >
                        <thead>
                          <tr>
                            {assistantMsg.columns.map((col) => (
                              <th
                                key={col}
                                className="border px-3 py-2 bg-gray-100 dark:bg-gray-700 text-left text-gray-700 dark:text-gray-100"
                              >
                                {col}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {assistantMsg.table.map((row, idx) => (
                            <tr key={idx}>
                              {assistantMsg.columns.map((col) => (
                                <td
                                  key={col}
                                  className="border px-3 py-2 bg-gray-100 dark:bg-gray-700 text-left text-gray-700 dark:text-gray-100"
                                >
                                  {row[col]}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {showChart[assistantMsg.id] &&
                        chartType[assistantMsg.id] && (
                          <div className="mt-4">
                            {renderChart(
                              assistantMsg,
                              chartType[assistantMsg.id]
                            )}
                          </div>
                        )}
                    </div>
                  )}

                  <div className="flex flex-wrap justify-end gap-2 mb-2">
                    <button
                      onClick={() => printTable(assistantMsg)}
                      className="p-2 rounded-md border dark:border-zinc-700 hover:bg-muted transition"
                      title="Imprimir tabla"
                    >
                      <TableProperties size={18} />
                    </button>

                    <button
                      onClick={() => downloadCSV(assistantMsg)}
                      className="p-2 rounded-md border dark:border-zinc-700 hover:bg-muted transition"
                      title="Descargar CSV"
                    >
                      <Download size={18} />
                    </button>

                    <button
                      onClick={() =>
                        setShowSQL((prev) => ({
                          ...prev,
                          [assistantMsg.id]: !prev[assistantMsg.id],
                        }))
                      }
                      className="p-2 rounded-md border dark:border-zinc-700 hover:bg-muted transition"
                      title={
                        showSQL[assistantMsg.id] ? "Ocultar SQL" : "Mostrar SQL"
                      }
                    >
                      <FilePenLine size={18} />
                    </button>

                    <button
                      onClick={() => {
                        setShowChart((prev) => ({
                          ...prev,
                          [assistantMsg.id]: !prev[assistantMsg.id],
                        }));
                        setChartType((prev) => ({
                          ...prev,
                          [assistantMsg.id]: prev[assistantMsg.id] || "Bar",
                        }));
                      }}
                      className="p-2 rounded-md border dark:border-zinc-700 hover:bg-muted transition"
                      title={
                        showChart[assistantMsg.id]
                          ? "Ocultar gráfico"
                          : "Mostrar gráfico"
                      }
                    >
                      <BarChart3 size={18} />
                    </button>

                    {showChart[assistantMsg.id] && (
                      <select
                        className="px-2 py-1 text-sm border border-gray-300 rounded-md dark:bg-gray-700 dark:text-white"
                        value={chartType[assistantMsg.id] || "Bar"}
                        onChange={(e) =>
                          setChartType((prev) => ({
                            ...prev,
                            [assistantMsg.id]: e.target.value,
                          }))
                        }
                      >
                        <option value="Bar">BarChart</option>
                        <option value="Line">LineChart</option>
                        <option value="Pie">PieChart</option>
                        <option value="Radar">RadarChart</option>
                      </select>
                    )}
                  </div>

                  {showSQL[assistantMsg.id] && (
                    <div className="mt-2 space-y-2">
                      <Editor
                        value={assistantMsg.sql}
                        onValueChange={(code) => {
                          const updatedMessages = messages.map((m) =>
                            m.id === assistantMsg.id ? { ...m, sql: code } : m
                          );
                          setMessages(updatedMessages);
                        }}
                        highlight={(code) =>
                          highlight(code, languages.sql, "sql")
                        }
                        padding={10}
                        className={`w-full text-sm font-mono rounded-md border ${
                          isDarkMode
                            ? "bg-[#1e1e1e] text-white border-gray-600"
                            : "bg-white text-black border-gray-300"
                        }`}
                        style={{
                          backgroundColor: isDarkMode ? "#1e1e1e" : "#f8f8f8",
                          minHeight: "200px",
                          whiteSpace: "pre-wrap",
                        }}
                      />

                      <div className="flex gap-2">
                        <button
                          onClick={async () => {
                            setIsLoading(true);
                            try {
                              const token =
                                sessionStorage.getItem("accessToken");

                              const res = await fetch(
                                `${
                                  import.meta.env.VITE_APP_API_URL_SQL
                                }/api/ask`,
                                {
                                  method: "POST",
                                  headers: {
                                    "Content-Type": "application/json",
                                    accept: "application/json",
                                    Authorization: `Bearer ${token}`,
                                  },
                                  body: JSON.stringify({
                                    question: userMsg.content,
                                    catalog: CATALOG,
                                    schema: selectedSchema,
                                    instructions: instructions,
                                    corrected_sql_query: assistantMsg.sql,
                                  }),
                                }
                              );

                              if (!res.ok)
                                throw new Error(
                                  "Error al ejecutar la consulta editada"
                                );

                              const data = await res.json();
                              logout(data?.detail || "");
                              const { answer, sql_result } = data;
                              const { columns, rows } =
                                parseSQLResult(sql_result);

                              const updatedMessages = messages.map((m) =>
                                m.id === assistantMsg.id
                                  ? { ...m, answer, columns, table: rows }
                                  : m
                              );
                              setMessages(updatedMessages);
                            } catch (err: any) {
                              logout(err?.status || "");
                              console.error(
                                "Error al ejecutar la consulta editada:",
                                err
                              );
                              alert("❌ Error al ejecutar la consulta");
                            } finally {
                              setIsLoading(false);
                            }
                          }}
                          className="p-2 rounded-md border dark:border-zinc-700 hover:bg-muted transition"
                          title="Ejecutar esta consulta"
                        >
                          <Play size={18} />
                        </button>

                        <button
                          onClick={async () => {
                            try {
                              const token =
                                sessionStorage.getItem("accessToken");

                              const res = await fetch(
                                `${
                                  import.meta.env.VITE_APP_API_URL
                                }/api/save-sql`,
                                {
                                  method: "POST",
                                  headers: {
                                    "Content-Type": "application/json",
                                    Authorization: `Bearer ${token}`,
                                    accept: "application/json",
                                  },
                                  body: JSON.stringify({
                                    question: userMsg.content,
                                    sql_query: assistantMsg.sql,
                                    catalog: CATALOG,
                                    db_schema: selectedSchema,
                                  }),
                                }
                              );
                              if (!res.ok)
                                throw new Error("Error al guardar la consulta");
                              alert("Consulta guardada correctamente ✅");
                            } catch (err: any) {
                              logout(err?.status || "");
                              console.error(
                                "Error al guardar la consulta:",
                                err
                              );
                              alert("❌ Error al guardar la consulta");
                            }
                          }}
                          className="p-2 rounded-md border dark:border-zinc-700 hover:bg-muted transition"
                          title="Guardar esta consulta"
                        >
                          <Save size={18} />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}

        {isLoading && (
          <div className="text-center text-gray-500 italic">⏳ Pensando...</div>
        )}

        <div
          ref={messagesEndRef}
          className="shrink-0 min-w-[24px] min-h-[24px]"
        />
      </div>

      <ChatInput
        question={question}
        setQuestion={setQuestion}
        onSubmit={handleSubmit}
        isLoading={isLoading}
        selectedSchema={selectedSchema}
        setSelectedSchema={setSelectedSchema}
        instructions={instructions}
        setInstructions={setInstructions}
        hasStartedChat={hasStartedChat}
      />
    </>
  );
}
