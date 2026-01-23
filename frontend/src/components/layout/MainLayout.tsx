import { Outlet } from "react-router-dom";
import { useState, useEffect } from "react"; // 1. Importar useEffect
import { Sidebar } from "../custom/sidebar";
import { Header } from "../custom/header";
import { ChatInterface } from "@/interfaces/interfaces";

type props = {
  chats: ChatInterface[];
  removeChatFromState: (chatId: string) => void;
  isLoading: boolean;
};

export function MainLayout({ chats, removeChatFromState, isLoading }: props) {
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
          isLoad={isLoading}
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
        <div className="flex-1 flex flex-col w-full h-screen bg-background items-center fixed lg:relative pb-4 pt-[57px] lg:pt-0">
          <Header setIsOpenNav={setIsOpen} />
          <Outlet />
        </div>
      </div>
    </>
  );
}
