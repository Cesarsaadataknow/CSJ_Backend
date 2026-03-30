import "./App.css";
import { ThemeProvider } from "./context/ThemeContext";
import { BrowserRouter } from "react-router-dom";
import PrivateRoutes from "./PrivateRoutes";
import { Toaster } from "sonner";
import { useEffect, useRef, useState } from "react";
import api from "./api/ApiGPT";

function App() {
  const [loading, setLoading] = useState(true);
  const hasInitialized = useRef(false);

  useEffect(() => {
    if (hasInitialized.current) return;
    hasInitialized.current = true;

    const initAuth = async () => {
      const urlParams = new URLSearchParams(window.location.search);
      const code = urlParams.get("code");

      if (code) {
        const consumedCode = sessionStorage.getItem("oauth_code_consumed");
        if (consumedCode === code) {
          window.history.replaceState({}, document.title, "/");
          setLoading(false);
          return;
        }

        const data = await api.requestToken(code);

        if (data?.access_token) {
          sessionStorage.setItem("oauth_code_consumed", code);
          localStorage.setItem("access_token", data.access_token);
          if (data.permissions != null) {
            localStorage.setItem("permissions", data.permissions);
          }

          window.history.replaceState({}, document.title, "/");
          setLoading(false);
        } else {
          window.history.replaceState({}, document.title, "/");
          setTimeout(() => api.requestLogin(), 1500);
        }
      } else {
        setTimeout(() => api.requestLogin(), 1500);
      }
    };

    initAuth();
  }, []);

  if (loading) return null;

  return (
    <ThemeProvider>
      <BrowserRouter>
        <PrivateRoutes />
      </BrowserRouter>
      <Toaster
        position="top-right"
        expand
        richColors
        className="flex flex-col gap-3"
      />
    </ThemeProvider>
  );
}

export default App;
