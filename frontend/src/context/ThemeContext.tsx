import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  Dispatch,
  SetStateAction,
} from "react";

interface ThemeContextType {
  modelSelect: string;
  setModelSelect: Dispatch<SetStateAction<string>>;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [modelSelect, setModelSelect] = useState(() => {
    const savedModel = localStorage.getItem("model");
    return savedModel ? savedModel : "gpt-4o";
  });

  useEffect(() => {
    if (!modelSelect) return;
    localStorage.setItem("model", modelSelect);
  }, [modelSelect]);

  return (
    <ThemeContext.Provider
      value={{ modelSelect, setModelSelect }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
