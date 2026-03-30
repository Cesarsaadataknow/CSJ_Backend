import { ReactNode, useEffect, useRef, useState, useMemo } from "react";
import { SquarePen, ChevronRight, ChevronLeft, Trash2, Search, Pencil, Check, X, LogOut, RefreshCw } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ChatInterface } from "@/interfaces/interfaces";
import api from "@/api/ApiGPT";
import UseLogout from "@/hooks/useLogout";
import ModalConfirmDelete from "../gpt/ModalConfirmDelete";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";

const LOGO_FLIP_INTERVAL_MS = 4500;
const LOGOS = [
  {
    src: "/logos/seccional/Logos Seccionales_DS Barranquilla.svg",
    isotipoSrc: "/favicon-csj-seccional-isotipo.png",
    alt: "Logo Consejo Superior de la Judicatura",
  },
  {
    src: "/LogoJusticiaYPaz.png",
    isotipoSrc: "/isotipo-justicia-y-paz.png",
    alt: "Logo Justicia y Paz",
  },
];

function LogoFlipCard({ onLinkClick, compact = false }: { onLinkClick: () => void; compact?: boolean }) {
  const [flipped, setFlipped] = useState(false);

  useEffect(() => {
    const id = setInterval(() => setFlipped((f) => !f), LOGO_FLIP_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  return (
    <Link
      to="/"
      className={`flex items-center justify-center shrink-0 overflow-hidden transition-all duration-300 [perspective:1000px] ${
        compact ? "h-20 px-1 pt-1 pb-1 mb-1" : "h-48 px-2 pt-0 pb-2 mb-1 -mt-8"
      }`}
      onClick={onLinkClick}
    >
      <div
        className="relative w-full h-full [transform-style:preserve-3d] transition-transform duration-700 ease-in-out"
        style={{ transform: flipped ? "rotateY(180deg)" : "rotateY(0deg)" }}
      >
        {LOGOS.map((logo, i) => (
          <div
            key={logo.src}
            className="absolute inset-0 flex items-center justify-center [backface-visibility:hidden]"
            style={{
              transform: i === 0 ? "rotateY(0deg)" : "rotateY(180deg)",
            }}
          >
            <img
              src={compact ? logo.isotipoSrc : logo.src}
              alt={logo.alt}
              className={`h-full w-full object-contain object-center ${
                compact ? "max-h-12" : i === 0 ? "max-h-24" : "max-h-[7.5rem]"
              }`}
            />
          </div>
        ))}
      </div>
    </Link>
  );
}

interface SidebarProps {
  isOpen: boolean;
  changeIsOpenNav: () => void;
  chats: ChatInterface[];
  removeChatFromState: (chatId: string) => void;
  renameChatInState: (chatId: string, newTitle: string) => void;
  isLoad: boolean;
  onRefreshChats?: () => void;
}
type typeChat = "c" | "sql";

export function Sidebar({
  isOpen,
  changeIsOpenNav,
  chats,
  removeChatFromState,
  renameChatInState,
  isLoad,
  onRefreshChats,
}: SidebarProps) {
  const { id: chatIdParam } = useParams<{ id: string }>();
  const { logout } = UseLogout();
  const [openModal, setOpenModal] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [deleteName, setDeleteName] = useState<string>("");
  const [loadingDelete, setLoadingDelete] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const searchInputRef = useRef<HTMLInputElement>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameText, setRenameText] = useState("");

  const navigate = useNavigate();

  const filteredChats = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) {
      return [...chats].sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
    }
    return [...chats]
      .filter((c) => c.title.toLowerCase().includes(query))
      .sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
  }, [chats, searchQuery]);

  /** Agrupa chats por fecha: Hoy, Ayer, Esta semana, Anteriores. Orden: más recientes primero. */
  const chatsByDateGroup = useMemo(() => {
    const now = new Date();
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const startOfYesterday = startOfToday - 24 * 60 * 60 * 1000;
    const startOfSevenDaysAgo = startOfToday - 7 * 24 * 60 * 60 * 1000;

    const groups: Record<string, ChatInterface[]> = {
      Hoy: [],
      Ayer: [],
      "Esta semana": [],
      Anteriores: [],
    };

    for (const chat of filteredChats) {
      const t = new Date(chat.created_at).getTime();
      if (t >= startOfToday) groups.Hoy.push(chat);
      else if (t >= startOfYesterday) groups.Ayer.push(chat);
      else if (t >= startOfSevenDaysAgo) groups["Esta semana"].push(chat);
      else groups.Anteriores.push(chat);
    }

    return [
      { label: "Hoy", chats: groups.Hoy },
      { label: "Ayer", chats: groups.Ayer },
      { label: "Esta semana", chats: groups["Esta semana"] },
      { label: "Anteriores", chats: groups.Anteriores },
    ];
  }, [filteredChats]);

  const createNewChat = () => {
    navigate("/");
    if (window.innerWidth < 1024 && isOpen) {
      changeIsOpenNav();
    }
  };

  const selectChat = (chatId: string, type: typeChat = "c") => {
    type == "c" ? navigate(`/c/${chatId}`) : navigate("/sql");
    if (window.innerWidth < 1024 && isOpen) {
      changeIsOpenNav();
    }
  };

  const [openProject, setOpenProject] = useState<boolean>(true);

  const onActiveProject = () => setOpenProject((prev: boolean) => !prev);

  const focusSearch = () => {
    changeIsOpenNav();
    setTimeout(() => searchInputRef.current?.focus(), 150);
  };

  const onDeleteConfirm = () => {
    if (!deleteId) return;
    setLoadingDelete(true);
    api
      .requestDeleteSession(deleteId)
      .then(() => {
        removeChatFromState(deleteId);
        chatIdParam == deleteId && navigate("/");
      })
      .catch((error) => {
        toast.error("Error al eliminar conversación");
        logout(error?.response?.statusText || "");
      })
      .finally(() => {
        setLoadingDelete(false);
        setOpenModal(false);
        setDeleteId(null);
        setDeleteName("");
      });
  };

  const startRenaming = (chatId: string, currentTitle: string) => {
    setRenamingId(chatId);
    setRenameText(currentTitle);
  };

  const confirmRename = () => {
    if (renamingId && renameText.trim()) {
      renameChatInState(renamingId, renameText);
    }
    setRenamingId(null);
    setRenameText("");
  };

  const cancelRename = () => {
    setRenamingId(null);
    setRenameText("");
  };

  return (
    <>
      <ModalConfirmDelete
        open={openModal}
        onClose={() => setOpenModal(false)}
        onConfirm={onDeleteConfirm}
        title="Eliminar chat"
        message="¿Seguro que deseas eliminar el siguiente chat?"
        itemName={deleteName}
        loading={loadingDelete}
      />

      <div
        className={`fixed z-50 lg:relative h-full bg-background gap-2 border-r border-gray-200 p-2 transition-all flex flex-col overflow-x-hidden
      ${
        isOpen
          ? "lg:w-64 w-8/12 top-0"
          : "w-0 -translate-x-full lg:w-28 lg:translate-x-0"
      }
    `}
      >
        {/* Logos con efecto flip en sidebar expandido/colapsado */}
        {isOpen ? (
          <LogoFlipCard
            onLinkClick={() => window.innerWidth < 1024 && changeIsOpenNav()}
          />
        ) : (
          <LogoFlipCard compact onLinkClick={() => {}} />
        )}
        {/* Botón de toggle: ChevronRight para expandir, ChevronLeft para colapsar */}
        <button
          type="button"
          onClick={changeIsOpenNav}
          className={`px-1 flex items-center justify-center ${!isOpen ? "w-full" : ""}`}
          aria-label={isOpen ? "Colapsar menú" : "Expandir menú"}
        >
          {isOpen ? (
            <ChevronLeft className="size-7" strokeWidth={1.5} />
          ) : (
            <ChevronRight className="size-7" strokeWidth={1.5} />
          )}
        </button>
        {/* Crear nueva conversación */}
        <SideBarItem
          icon={<SquarePen size={22} />}
          text={isOpen ? "Nueva conversación" : ""}
          active={false}
          onActive={createNewChat}
          ariaLabel="Nueva conversación"
        />
        {/* Icono búsqueda visible también con sidebar colapsado */}
        {!isOpen && (
          <SideBarItem
            icon={<Search size={22} />}
            text=""
            active={false}
            onActive={focusSearch}
            ariaLabel="Buscar conversaciones"
          />
        )}
        <div className="flex-1 gap-2 overflow-y-auto">
          {/* SQL */}
          {/* <div>
            <SideBarItem
              icon={<Database size={22} />}
              text={isOpen ? "SQL" : ""}
              active={location.pathname == "/sql"}
              onActive={() => selectChat("", "sql")}
              isSticky={true}
            />
          </div> */}

          {/* Lista de chats */}
          {isLoad && (
            <>
              <div className={`space-y-2 animate-pulse`}>
                {/* Generamos 5 items de esqueleto */}
                {Array(5)
                  .fill(0)
                  .map((_, index) => (
                    <SkeletonItem key={index} /> // Ya no necesitamos pasar isDarkMode
                  ))}
              </div>
            </>
          )}
          <div
            className={`transition-all duration-400 ease-in-out ${
              isOpen ? "opacity-100" : "opacity-0"
            }`}
          >
            <div className="flex items-center justify-between w-full gap-1">
              <button
                type="button"
                className="text-sm font-semibold p-2 flex justify-start items-center flex-1 min-w-0"
                onClick={onActiveProject}
                aria-expanded={openProject}
                aria-label={openProject ? "Colapsar sección Chats" : "Expandir sección Chats"}
              >
                Chats
                <div
                  className={`ml-1 transform transition-transform duration-500 ease-in-out ${
                    openProject ? "rotate-90" : "rotate-0"
                  }`}
                >
                  <ChevronRight strokeWidth={1.25} size={18} />
                </div>
              </button>
              {onRefreshChats && (
                <button
                  type="button"
                  onClick={onRefreshChats}
                  className="shrink-0 p-2 rounded-lg text-neutral-600 hover:bg-neutral-200 hover:text-neutral-800 transition-colors"
                  aria-label="Refrescar lista de conversaciones"
                  title="Refrescar lista de conversaciones"
                >
                  <RefreshCw className="size-4" aria-hidden />
                </button>
              )}
            </div>
            <div
              className={`transition-all duration-400 ease-in-out ${
                openProject ? "opacity-100" : "opacity-0"
              }`}
            >
              {isOpen && (
                <div className="px-2 pb-2">
                  <div className="relative">
                    <Search
                      className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground pointer-events-none"
                      aria-hidden
                    />
                    <Input
                      ref={searchInputRef}
                      type="search"
                      placeholder="Buscar por título..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pl-8 h-9 text-sm"
                      aria-label="Buscar conversaciones por título"
                    />
                  </div>
                </div>
              )}
              {chats.length === 0 && !isLoad ? (
                <p className="text-xs text-muted-foreground px-2 py-3">
                  Aún no hay conversaciones. Crea una con «Nueva conversación».
                </p>
              ) : filteredChats.length === 0 ? (
                <p className="text-xs text-muted-foreground px-2 py-3">
                  {searchQuery.trim()
                    ? `Sin resultados para "${searchQuery.trim()}"`
                    : "Aún no hay conversaciones. Crea una con «Nueva conversación»."}
                </p>
              ) : (
                <div className="overflow-y-auto transition-all duration-500 ease-in-out space-y-3">
                  {chatsByDateGroup.map(
                    ({ label, chats: groupChats }) =>
                      groupChats.length > 0 && (
                        <div key={label}>
                          <p className="text-xs font-medium text-muted-foreground px-2 py-1 sticky top-0 bg-background/95">
                            {label}
                          </p>
                          {groupChats.map(({ chatId, title }) => (
                            <SideBarItem
                              key={chatId}
                              text={title}
                              active={chatId == chatIdParam}
                              onActive={() => selectChat(chatId)}
                              onDelete={() => {
                                setDeleteId(chatId);
                                setDeleteName(title);
                                setOpenModal(true);
                              }}
                              onRename={() => startRenaming(chatId, title)}
                              isRenaming={renamingId === chatId}
                              renameText={renameText}
                              onRenameTextChange={setRenameText}
                              onRenameConfirm={confirmRename}
                              onRenameCancel={cancelRename}
                            />
                          ))}
                        </div>
                      )
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
        {/* Botón cerrar sesión */}
        <div className={`border-t border-gray-200 pt-2 ${isOpen ? "" : "hidden"}`}>
          <button
            type="button"
            onClick={() => logout("")}
            className="flex items-center gap-2 w-full p-2 rounded-lg text-sm text-neutral-700 hover:bg-neutral-200 transition-all"
            aria-label="Cerrar sesión"
          >
            <LogOut size={18} aria-hidden />
            <span>Cerrar sesión</span>
          </button>
        </div>
      </div>
    </>
  );
}

/* ===============================
   COMPONENTE HIJO: SideBarItem
   =============================== */
type PropsSideBarItem = {
  icon?: ReactNode;
  text: string;
  active?: boolean;
  onActive: () => void;
  isSticky?: boolean;
  onDelete?: (() => void) | null;
  onRename?: (() => void) | null;
  isRenaming?: boolean;
  renameText?: string;
  onRenameTextChange?: (value: string) => void;
  onRenameConfirm?: () => void;
  onRenameCancel?: () => void;
  ariaLabel?: string;
};

const SideBarItem = ({
  text,
  icon,
  active = false,
  onActive,
  isSticky = false,
  onDelete = null,
  onRename = null,
  isRenaming = false,
  renameText = "",
  onRenameTextChange,
  onRenameConfirm,
  onRenameCancel,
  ariaLabel,
}: PropsSideBarItem) => {
  const itemRef = useRef<HTMLButtonElement | null>(null);
  const [isStickyActive, setIsStickyActive] = useState(false);

  useEffect(() => {
    if (!isSticky || !itemRef.current) return;

    const el = itemRef.current;
    const observer = new IntersectionObserver(
      ([entry]) => {
        // Cuando deja de estar completamente visible (se “pega” al top)
        setIsStickyActive(!entry.isIntersecting);
      },
      { rootMargin: "-1px 0px 0px 0px", threshold: [1] }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [isSticky]);

  return (
    <button
      ref={itemRef}
      aria-label={ariaLabel}
      className={`flex flex-row items-center w-full p-2 gap-2 rounded-lg text-sm text-neutral-700 font-normal transition-all duration-300
      ${text ? "justify-between" : "justify-center"} group
      ${
        active
          ? "bg-[#85bbf8] !text-[#153f70] font-semibold"
          : "bg-transparent hover:bg-neutral-200"
      }
      ${isSticky ? "sticky top-0" : ""}
      ${isStickyActive ? "border-b border-gray-300 shadow-sm bg-white" : ""}`}
      onClick={isRenaming ? undefined : onActive}
      style={text ? {} : { placeContent: "center" }}
    >
      <div className={`flex gap-2 min-w-0 flex-1 ${!text ? "justify-center" : ""}`}>
        {icon && <div className="w-fit shrink-0">{icon}</div>}
        {isRenaming ? (
          <input
            type="text"
            value={renameText}
            onChange={(e) => onRenameTextChange?.(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") onRenameConfirm?.();
              if (e.key === "Escape") onRenameCancel?.();
            }}
            onClick={(e) => e.stopPropagation()}
            className="bg-white border border-gray-300 rounded px-1 py-0.5 text-sm w-full outline-none focus:border-blue-400"
            autoFocus
          />
        ) : (
          text && <span className="text-nowrap truncate" title={text}>{text}</span>
        )}
      </div>
      {isRenaming ? (
        <div className="flex gap-1 shrink-0">
          <Check
            size={16}
            onClick={(e) => {
              e.stopPropagation();
              onRenameConfirm?.();
            }}
            className="cursor-pointer text-green-600 hover:text-green-800"
          />
          <X
            size={16}
            onClick={(e) => {
              e.stopPropagation();
              onRenameCancel?.();
            }}
            className="cursor-pointer text-red-500 hover:text-red-700"
          />
        </div>
      ) : (onDelete || onRename) ? (
        <div className="flex gap-1 shrink-0">
          {onRename && (
            <Pencil
              size={16}
              onClick={(e) => {
                e.stopPropagation();
                onRename();
              }}
              className="z-40 hidden lg:group-hover:flex cursor-pointer"
            />
          )}
          {onDelete && (
            <Trash2
              height={20}
              onClick={(e) => {
                e.stopPropagation();
                onDelete();
              }}
              className="z-40 flex lg:hidden lg:group-hover:flex"
            />
          )}
        </div>
      ) : null}
    </button>
  );
};

const SkeletonItem = () => (
  <div
    className={`
        h-6 rounded-full w-full
        bg-gray-300
      `}
  />
);
