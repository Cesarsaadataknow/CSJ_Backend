// src/App.tsx
import "./App.css";
import { ThemeProvider } from "./context/ThemeContext";
import {
  BrowserRouter,
  createBrowserRouter,
  RouterProvider,
} from "react-router-dom";
import Login from "./pages/login/Login";
import {
  AuthenticatedTemplate,
  MsalProvider,
  UnauthenticatedTemplate,
} from "@azure/msal-react";
import { msalInstance } from "./config/msalConfig";
import PrivateRoutes from "./PrivateRoutes";
import { Toaster } from "sonner";

const routerPublic = createBrowserRouter([
  {
    path: "*",
    element: <Login />,
  },
]);

function App() {
  return (
    // <MsalProvider instance={msalInstance}>
      <ThemeProvider>
        {/* <UnauthenticatedTemplate>
          <RouterProvider router={routerPublic} />
        </UnauthenticatedTemplate> */}

        {/* <AuthenticatedTemplate> */}
          <BrowserRouter>
            <PrivateRoutes />
          </BrowserRouter>
        {/* </AuthenticatedTemplate> */}
      </ThemeProvider>
    //  <Toaster />
    // </MsalProvider>
  );
}

export default App;
