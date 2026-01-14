// src/components/custom/LogoutButton.tsx
import { useMsal } from "@azure/msal-react";
import { Button } from "@/components/ui/button";
import { LogOut } from 'lucide-react';


export function LogoutButton() {
    const { instance } = useMsal();

    const handleLogout = () => {
        sessionStorage.removeItem("accessToken"); // Opcional
        instance.logoutRedirect({
            postLogoutRedirectUri: "/", // Cambia si quieres redirigir a /login
        });
    };

    return (
        <Button
            variant="outline"
            className="border border-gray text-red-600 hover:bg-red-600 hover:text-white flex items-center gap-2 h-10 transition-colors" // "bg-background border border-gray text-gray-600 hover:white h-10"
            onClick={handleLogout}
        >
            Cerrar sesión
            <LogOut className="h-[1.2rem] w-[1.2rem]" />
        </Button>
    );
}
