import {
  useState,
  useEffect,
  useRef,
  DragEvent,
  ClipboardEvent,
  Dispatch,
  SetStateAction,
} from "react";
import { Textarea } from "../ui/textarea";
import { Button } from "../ui/button";
import { toast } from "sonner";
import { cx } from "classix";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowUpIcon, Paperclip } from "lucide-react";
import ListFile from "../custom/ListFile";
import { StopIcon } from "../custom/icons";

interface ChatInputProps {
  question: string;
  setQuestion: (value: string) => void;
  onSubmit: (params: {
    text: string;
    idMessageCorrected?: string | undefined;
    isUpdate?: boolean | undefined;
    is_regenerate: boolean;
    files: File[];
  }) => void;
  isLoading: boolean;
  instructions: string;
  setInstructions: (value: string) => void;
  hasStartedChat: boolean;
  files: File[];
  setFiles: Dispatch<SetStateAction<File[]>>;
  handleStop: () => void;
}
const MAX_FILES = 10;

export const InputGPT = ({
  question,
  setQuestion,
  onSubmit,
  isLoading,
  files,
  setFiles,
  handleStop,
}: ChatInputProps) => {
  const [isDraggingGlobal, setIsDraggingGlobal] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  // 🟢 Detecta drag & drop global, pero muestra overlay solo en el box
  useEffect(() => {
    let dragCounter = 0;

    const handleDragEnter = (e: DragEvent) => {
      e.preventDefault();
      dragCounter++;
      if (e.dataTransfer?.types.includes("Files")) {
        setIsDraggingGlobal(true);
      }
    };

    const handleDragLeave = (e: DragEvent) => {
      e.preventDefault();
      dragCounter--;
      if (dragCounter <= 0) {
        setIsDraggingGlobal(false);
      }
    };

    const handleDrop = (e: DragEvent) => {
      e.preventDefault();
      dragCounter = 0;
      setIsDraggingGlobal(false);

      const droppedFiles = Array.from(e.dataTransfer?.files || []);
      if (droppedFiles.length) {
        // setFiles((prev) => [...prev, ...droppedFiles]);
        addFiles(droppedFiles);
        toast.success(`${droppedFiles.length} archivo(s) agregado(s)`);
      }
    };

    window.addEventListener("dragenter", handleDragEnter as any);
    window.addEventListener("dragleave", handleDragLeave as any);
    window.addEventListener("dragover", (e) => e.preventDefault());
    window.addEventListener("drop", handleDrop as any);

    return () => {
      window.removeEventListener("dragenter", handleDragEnter as any);
      window.removeEventListener("dragleave", handleDragLeave as any);
      window.removeEventListener("dragover", (e) => e.preventDefault());
      window.removeEventListener("drop", handleDrop as any);
    };
  }, []);

  // 🟩 Manejo de pegado (Ctrl+V)
  const handlePaste = (e: ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData.items;
    const pastedFiles: File[] = [];
    for (const item of items) {
      if (item.kind === "file") {
        const file = item.getAsFile();
        if (file) pastedFiles.push(file);
      }
    }
    if (pastedFiles.length) {
      addFiles(pastedFiles);
      // setFiles((prev) => [...prev, ...pastedFiles]);
      toast.success(`${pastedFiles.length} archivo(s) pegado(s)`);
    }
  };

  // 🟥 Eliminar archivo
  const handleRemoveFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  // 🚀 Enviar mensaje + archivos
  const handleSend = () => {
    if (isLoading) {
      toast.error("Por favor espera la respuesta del modelo");
      return;
    }

    if (!question.trim() && files.length === 0) {
      toast.error("Debes escribir un mensaje o adjuntar un archivo");
      return;
    }

    onSubmit({
      text: question,
      is_regenerate: false,
      files: files,
    });
    setQuestion("");
    setFiles([]);
  };

  const addFiles = (incomming: File[]) => {
    setFiles((prev) => {
      const amountMissing = MAX_FILES - prev.length;
      if (amountMissing <= 0) {
        toast.error("Máximo 10 archivos permitidos");
        return prev;
      }
      if (incomming.length > amountMissing) {
        const filePermitted = incomming.slice(0, amountMissing);
        toast.error("Máximo 10 archivos permitidos");

        return [...prev, ...filePermitted];
      }

      return [...prev, ...incomming];
    });
  };
  return (
    <div className="max-w-4xl w-full px-2 sticky bottom-0">
      <div
        ref={boxRef}
        className="relative w-full rounded-xl bg-muted border lg:mx-auto px-4 gap-2"
      >
        {/* Archivos cargados */}
        {files.length > 0 && (
          <div className="flex flex-wrap gap-2 p-2 border-b border-zinc-300 bg-zinc-50">
            <ListFile files={files} onRemove={handleRemoveFile} />
          </div>
        )}

        {/* Textarea */}
        <Textarea
          placeholder="Escribe una consulta o pega un archivo..."
          className={cx(
            "w-full min-h-[48px] max-h-[60dvh] resize-none text-base",
            "bg-muted border-0 focus:ring-0 focus:outline-none",
            "px-3 py-3 leading-normal"
          )}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onPaste={handlePaste}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              handleSend();
            }
          }}
          rows={3}
          autoFocus
        />

        {/* Barra de acciones */}
        <div className="w-full flex justify-between px-[12px] py-[8px]">
          <div className="flex flex-row gap-2 items-center">
            <Button
              variant="outline"
              onClick={() => fileInputRef.current?.click()}
            >
              <Paperclip size={16} />
              <span className="hidden lg:block">Archivos</span>
            </Button>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              hidden
              onChange={(e) => {
                const newFiles = Array.from(e.target.files || []);
                if (newFiles.length) addFiles(newFiles);
              }}
            />
            {/* <Button
              variant="outline"
              className={
                isSearch
                  ? "bg-blue-500/45 !text-blue-900 border border-blue-600 hover:bg-blue-400/45 "
                  : ""
              }
              onClick={() => setIsSearch((prev) => !prev)}
            >
              <Globe />
              <span className="hidden lg:block">Buscar</span>
            </Button> */}
          </div>
          <div className="flex flex-row gap-2">
            {/* <DropdownModel setValue={setModelSelect} value={modelSelect} /> */}
            {!question.length ||
              (!isLoading && (
                <Button
                  className="cursor-pointer rounded-full p-1.5 h-fit bottom-2 right-2 border z-50"
                  onClick={isLoading ? handleStop : handleSend}
                >
                  {isLoading ? <StopIcon /> : <ArrowUpIcon size={14} />}
                </Button>
              ))}
          </div>
        </div>

        {/* 🟦 Overlay dentro del box */}
        <AnimatePresence>
          {isDraggingGlobal && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="absolute inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm text-white text-lg font-semibold border-2 border-dashed border-white rounded-xl"
            >
              📂 Suelta los archivos aquí
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};
