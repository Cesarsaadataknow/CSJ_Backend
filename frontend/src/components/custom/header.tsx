import { Dispatch } from "react";
import { LogoutButton } from "./LogoutButton";
import { Link } from "react-router-dom";

type Props = {
  setIsOpenNav: Dispatch<React.SetStateAction<boolean>>;
};
export const Header = ({ setIsOpenNav }: Props) => {

  return (
    <>
      <header className="absolute lg:relative w-ful flex items-center px-3 sm:px-4 py-2  text-black w-full top-0 z-20 bg-background border-b border-neutral-300 justify-between mb-[57px] lg:mb-0">
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
          <img src={"/logo.png"} alt="Logo" className="mx-auto h-20" />
        </Link>
        <div className="flex flex-row gap-2">
          {/* <LogoutButton /> */}
        </div>
      </header>
    </>
  );
};
