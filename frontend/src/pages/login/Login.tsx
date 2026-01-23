import { useMsal } from "@azure/msal-react";
import { loginRequest } from "../../config/msalConfig";
import logoMicrosoft from "@/assets/microsoft-logo.svg";
import { toast } from "sonner";

export default function Login() {
  const { instance } = useMsal();

  const handleLogin = async () => {
    try {
      await instance.loginRedirect(loginRequest);

      const account = instance.getAllAccounts()[0];
      if (account) {
        const response = await instance.acquireTokenSilent({
          ...loginRequest,
          account,
        });
        sessionStorage.setItem("accessToken", response.accessToken);
      }
    } catch (e) {
      console.error(e);
      toast.error("Error al iniciar sesión");
    }
  };

  return (
    <div
      className="
    min-h-screen w-full flex items-center justify-center
    bg-gradient-to-br from-[#ffffff] via-[#f3f4f6] to-[#e5e7eb]
    text-[#0f3a64] px-6
  "
    >
      {/* Contenedor central */}
      <div className="w-full max-w-md text-center flex flex-col items-center">
        {/* Logo con halo dorado */}
        <div className="mb-10 relative flex justify-center">
          {/* Halo */}
          <div className="absolute -inset-4 rounded-full bg-[#c9a24d]/20 blur-xl"></div>

          {/* Logo */}
          <div className="relative">
            <img
              src="/logo.png"
              alt="Logo Corte Suprema de Justicia"
              className="h-[120px] object-contain"
            />
          </div>
        </div>

        {/* Descripción */}
        <p className="text-gray-600 text-sm mb-10 max-w-sm">
          Plataforma de análisis inteligente para decisiones estratégicas.
        </p>

        {/* Botón login */}
        <button
          onClick={handleLogin}
          className="
        w-full flex items-center justify-center gap-3
        bg-[#0f3a64]
        py-3 rounded-lg
        hover:bg-[#124a82]
        transition-colors
        font-medium
        text-white
        shadow-xl
      "
        >
          <img src={logoMicrosoft} alt="Microsoft" className="w-5 h-5" />
          Iniciar sesión con Microsoft
        </button>

        {/* Texto soporte */}
        <p className="text-xs text-gray-500 mt-4">
          Contacta al administrador para obtener acceso.
        </p>
      </div>
    </div>
  );
}
