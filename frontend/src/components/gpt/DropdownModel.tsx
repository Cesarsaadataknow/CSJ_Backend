import React, { useEffect, useRef, useState } from "react";

type Option = {
  value: string;
  label: string;
  description: string;
};

const MODELS: Option[] = [
  {
    value: "gpt-4o",
    label: "GPT-4o",
    description: "Estable, ideal para tareas generales",
  },
  {
    value: "gpt-5-chat",
    label: "GPT-5",
    description: "Más rápido, mejor razonamiento y contexto",
  },
];

type Props = {
  setValue: React.Dispatch<React.SetStateAction<string>>;
  value: string;
};

export default function DropdownModel({ value, setValue }: Props) {
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Inicializar desde localStorage
  useEffect(() => {
    const saved = localStorage.getItem("model");
    if (saved) {
      setValue(saved);
    } else {
      setValue("gpt-4o");
      localStorage.setItem("model", "gpt-4o");
    }
  }, [setValue]);

  // Cerrar al hacer clic fuera
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleDropdown = (newValue: string) => {
    if (value !== newValue) {
      setValue(newValue);
      localStorage.setItem("model", newValue);
    }
    setOpen(false);
  };

  const current = MODELS.find((m) => m.value === value);

  return (
    <>
      {/* Fondo oscuro móvil */}
      <div
        onClick={() => setOpen(false)}
        className={`fixed inset-0 bg-black z-40 lg:hidden transition-opacity duration-300 ease-in-out ${
          open ? "opacity-50" : "opacity-0 pointer-events-none"
        }`}
      ></div>

      <div ref={dropdownRef} className="relative inline-block text-left">
        {/* Menú desplegable */}
        {open && (
          <div className="fixed lg:absolute bottom-0 lg:bottom-full left-0 lg:left-auto lg:right-0 z-[1000] lg:w-60 w-full h-[200px] mt-2 bg-neutral-50 border border-default-medium rounded-b-none lg:rounded-lg lg:mb-1 shadow-lg">
            <ul className="p-2 text-sm text-body font-medium">
              {MODELS.map(({ value: val, label, description }) => (
                <li key={val}>
                  <button
                    onClick={() => handleDropdown(val)}
                    className={`w-full text-start p-2 rounded transition ${
                      value === val ? "bg-neutral-200" : "hover:bg-neutral-200"
                    }`}
                  >
                    <h4 className="font-semibold text-lg">{label}</h4>
                    <span className="font-normal text-sm text-neutral-700">
                      {description}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Botón principal */}
        <button
          onClick={() => setOpen((prev) => !prev)}
          className="inline-flex items-center justify-center border border-input bg-background hover:opacity-70 hover:text-accent-foreground h-10 px-4 py-2 text-sm font-medium rounded-md transition"
          type="button"
        >
          {current?.label ?? "GPT-4o"}
          <svg
            className={`w-4 h-4 ms-1.5 -me-0.5 transition-transform ${
              open ? "rotate-180" : "rotate-0"
            }`}
            aria-hidden="true"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <path
              stroke="currentColor"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="m19 9-7 7-7-7"
            />
          </svg>
        </button>
      </div>
    </>
  );
}
