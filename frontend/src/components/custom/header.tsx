import { Dispatch } from "react";
import { ThemeToggle } from "./theme-toggle";
import { LogoutButton } from "./LogoutButton";
import { Link } from "react-router-dom";
import { useTheme } from "@/context/ThemeContext";

type Props = {
  setIsOpenNav: Dispatch<React.SetStateAction<boolean>>;
};
export const Header = ({ setIsOpenNav }: Props) => {
    const { isDarkMode } = useTheme()

  return (
    <>
      <header className="absolute lg:relative w-ful flex items-center px-3 sm:px-4 py-2  text-black dark:text-white w-full top-0 z-20 bg-background border-b border-neutral-300 dark:border-neutral-800 justify-between mb-[57px] lg:mb-0">
        <button
          className="block lg:hidden mr-1"
          onClick={() => setIsOpenNav((prev: boolean) => !prev)}
        >
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

        <Link to="/">
          <img src={isDarkMode ? "/SofIA_Blanco.png" : "/SofIA_Color.png"} alt="Logo" className="mx-auto h-10" />
        </Link>
        <div className="flex flex-row gap-2">
          <ThemeToggle />
          <LogoutButton />
        </div>
      </header>
    </>
  );
};
