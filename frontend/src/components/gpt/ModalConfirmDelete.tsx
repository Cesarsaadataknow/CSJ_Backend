import { useEffect, useRef } from "react";

type Props = {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title?: string;
  message?: string;
  itemName?: string; // ← nombre del chat
  loading?: boolean; // ← estado de carga
};

export default function ModalConfirmDelete({
  open,
  onClose,
  onConfirm,
  title = "Eliminar chat",
  message = "¿Seguro que deseas eliminar este chat?",
  itemName = "",
  loading = false,
}: Props) {
  const modalRef = useRef<HTMLDivElement | null>(null);

  // Bloquear scroll en el fondo
  useEffect(() => {
    if (open) document.body.style.overflow = "hidden";
    else document.body.style.overflow = "auto";

    return () => {
      document.body.style.overflow = "auto";
    };
  }, [open]);

  // Cerrar con ESC
  useEffect(() => {
    if (!open) return;

    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [open, onClose]);

  // Cerrar cliqueando afuera
  const handleOutside = (e: React.MouseEvent) => {
    if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
      onClose();
    }
  };

  if (!open) return null;

  return (
    <div
      onClick={handleOutside}
      className="fixed inset-0 bg-black/50 flex justify-center items-center z-[2000]"
    >
      <div
        ref={modalRef}
        className="bg-white dark:bg-neutral-800 rounded-lg shadow-lg p-6 w-80 animate-fadeIn"
      >
        <h2 className="font-semibold text-lg mb-2 text-neutral-900 dark:text-neutral-100">
          {title}
        </h2>

        <p className="text-sm text-neutral-700 dark:text-neutral-300 mb-4">
          {message}
          <span className="font-bold text-red-600">{" " + itemName}</span>
        </p>

        <div className="flex justify-end gap-3">
          <button
            disabled={loading}
            className="px-3 py-2 rounded-md text-sm bg-neutral-200 hover:bg-neutral-300 
            dark:bg-neutral-700 dark:hover:bg-neutral-600 disabled:opacity-50"
            onClick={onClose}
          >
            Cancelar
          </button>

          <button
            disabled={loading}
            className="px-3 py-2 rounded-md text-sm bg-red-600 hover:bg-red-700 text-white 
            disabled:opacity-50"
            onClick={onConfirm}
          >
            {loading ? "Eliminando..." : "Eliminar"}
          </button>
        </div>
      </div>
    </div>
  );
}
