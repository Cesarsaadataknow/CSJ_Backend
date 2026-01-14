import { ReactNode, useEffect, useRef, useState } from "react";
import { SquarePen, ChevronRight, Trash2 } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { ChatInterface } from "@/interfaces/interfaces";
import api from "@/api/ApiGPT";
import UseLogout from "@/hooks/useLogout";
import ModalConfirmDelete from "../gpt/ModalConfirmDelete";
import { toast } from "sonner";

interface SidebarProps {
  isOpen: boolean;
  changeIsOpenNav: () => void;
  chats: ChatInterface[];
  removeChatFromState: (chatId: string) => void;
  isLoad: boolean;
}
type typeChat = "c" | "sql";

export function Sidebar({
  isOpen,
  changeIsOpenNav,
  chats,
  removeChatFromState,
  isLoad,
}: SidebarProps) {
  const { id: chatIdParam } = useParams<{ id: string }>();
  const { logout } = UseLogout();
  const [openModal, setOpenModal] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [deleteName, setDeleteName] = useState<string>(""); // ← nuevo
  const [loadingDelete, setLoadingDelete] = useState(false); // ← nuevo

  const navigate = useNavigate();

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
          ? "lg:w-3/12 w-8/12 top-0"
          : "w-0 -translate-x-full lg:w-[50px] lg:translate-x-0"
      }
    `}
      >
        {/* Botón de toggle */}
        <button onClick={changeIsOpenNav} className="px-1">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
            className="size-7"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M3.75 9h16.5m-16.5 6.75h16.5"
            />
          </svg>
        </button>
        {/* Crear nueva conversación */}
        <SideBarItem
          icon={<SquarePen size={22} />}
          text={isOpen ? "Nueva conversación" : ""}
          active={false}
          onActive={createNewChat}
        />
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
            hidden={chats.length == 0}
          >
            <button
              className="text-sm font-semibold p-2 w-full flex justify-start items-center"
              onClick={onActiveProject}
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
            <div
              className={`transition-all duration-400 ease-in-out ${
                openProject ? "opacity-100" : "opacity-0"
              }`}
            >
              <div
                className={`overflow-y-auto transition-all duration-500 ease-in-out`}
              >
                {chats
                  .sort(
                    (a, b) =>
                      new Date(b.created_at).getTime() -
                      new Date(a.created_at).getTime()
                  )
                  .map(({ chatId, title }) => (
                    <SideBarItem
                      key={chatId}
                      text={title}
                      active={chatId == chatIdParam}
                      onActive={() => {
                        selectChat(chatId);
                      }}
                      onDelete={() => {
                        setDeleteId(chatId);
                        setDeleteName(title); // ← nombre del chat
                        setOpenModal(true);
                      }}
                    />
                  ))}
              </div>
            </div>
          </div>
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
};

const SideBarItem = ({
  text,
  icon,
  active = false,
  onActive,
  isSticky = false,
  onDelete = null,
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
      className={`flex flex-row items-center w-full p-2 gap-2 rounded-lg text-sm text-neutral-700 font-normal transition-all duration-300
      justify-between group
      ${
        active
          ? "bg-[#85bbf8] !text-[#153f70] font-semibold"
          : "bg-transparent hover:bg-neutral-200"
      }
      ${isSticky ? "sticky top-0" : ""}
      ${isStickyActive ? "border-b border-gray-300 shadow-sm bg-white" : ""}`}
      onClick={onActive}
      style={text ? {} : { placeContent: "center" }}
    >
      <div className="flex gap-2">
        {icon && <div className="w-fit">{icon}</div>}
        {text && <span className="text-nowrap">{text}</span>}
      </div>
      {onDelete && (
        <Trash2
          height={20}
          onClick={(e) => {
            e.stopPropagation(); // Detiene el evento aquí, no llega al padre
            onDelete();
          }}
          className="z-40 flex lg:hidden lg:group-hover:flex"
        />
      )}
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
