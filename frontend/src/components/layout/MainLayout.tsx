import { Outlet } from "react-router-dom";
import { useState, useEffect } from "react";
import { ChevronRight } from "lucide-react";
import { Sidebar } from "../custom/sidebar";
import { ChatInterface } from "@/interfaces/interfaces";

type props = {
  chats: ChatInterface[];
  removeChatFromState: (chatId: string) => void;
  renameChatInState: (chatId: string, newTitle: string) => void;
  isLoading: boolean;
  onRefreshChats?: () => void;
};

export function MainLayout({ chats, removeChatFromState, renameChatInState, isLoading, onRefreshChats }: props) {
  // 2. Inicializar el estado comprobando el ancho de la ventana
  const [isOpen, setIsOpen] = useState(() => {
    // Si el ancho es mayor a 1024px (Desktop), inicia en true. Si no, false.
    return window.innerWidth >= 1024;
  });

  // 3. Escuchar cambios de tamaño de pantalla
  useEffect(() => {
    const mediaQuery = window.matchMedia("(min-width: 1024px)");

    const handleMediaChange = (event: MediaQueryListEvent) => {
      setIsOpen(event.matches); // Se abre si es desktop, se cierra si es mobile
    };

    // Escuchar el evento
    mediaQuery.addEventListener("change", handleMediaChange);
    return () => mediaQuery.removeEventListener("change", handleMediaChange);
  }, []);

  const toggleSidebar = () => setIsOpen((prev) => !prev);

  return (
    <>
      <div className="w-full h-screen flex flex-row overflow-hidden transition-all">
        <Sidebar
          isOpen={isOpen}
          changeIsOpenNav={toggleSidebar}
          chats={chats}
          removeChatFromState={removeChatFromState}
          renameChatInState={renameChatInState}
          isLoad={isLoading}
          onRefreshChats={onRefreshChats}
        />
        <div
          role="button"
          tabIndex={0}
          aria-label="Cerrar menú"
          onClick={toggleSidebar}
          onKeyDown={(e) => e.key === "Escape" && toggleSidebar()}
          className={`
                fixed inset-0 bg-black z-40 lg:hidden
                transition-opacity duration-300 ease-in-out
                ${isOpen ? "opacity-50" : "opacity-0 pointer-events-none"}
                `}
        ></div>
        <div className="flex-1 flex flex-col w-full h-screen bg-background items-center fixed lg:relative pb-4 pt-4 lg:pt-4">
          {/* Botón menú móvil: solo visible cuando el sidebar está cerrado */}
          <button
            type="button"
            onClick={toggleSidebar}
            className="fixed top-3 left-3 z-30 lg:hidden flex items-center justify-center w-10 h-10 rounded-lg bg-background border border-neutral-300 shadow-sm text-neutral-700 hover:bg-neutral-100"
            aria-label="Abrir menú"
          >
            <ChevronRight className="size-6" strokeWidth={1.5} />
          </button>
          <Outlet />
        </div>
      </div>
    </>
  );
}
