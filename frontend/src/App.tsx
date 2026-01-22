import "./App.css";
import { ThemeProvider } from "./context/ThemeContext";
import { BrowserRouter } from "react-router-dom";
import PrivateRoutes from "./PrivateRoutes";
import { Toaster } from "sonner";
import { useEffect, useState } from "react";
import api from "./api/ApiGPT";

function App() {
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      const urlParams = new URLSearchParams(window.location.search);
      const code = urlParams.get("code");

      if (localStorage.getItem("access_token")) {
        setLoading(false);
        return;
      }

      if (code) {
        const data = await api.requestToken(code);

        if (data?.access_token) {
          localStorage.setItem("access_token", data.access_token);
          localStorage.setItem("permissions", data.permissions);

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
      <Toaster />
    </ThemeProvider>
  );
}

export default App;
