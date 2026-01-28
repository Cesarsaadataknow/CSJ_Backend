import { User } from "@/interfaces/interfaces";
import { useMsal } from "@azure/msal-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

export default function UseLogout() {
  const { instance, accounts } = useMsal();
  const [user, setUser] = useState<User | null>(null);

  const logout = (status: string | number) => {
    // const status =
    //   err.response?.statusText ??
    //   err.response?.data?.detail ??
    //   err.detail ??
    //   '';

    if (
      status === "Unauthorized" ||
      status === "Token inválido" ||
      status === "Token expirado" ||
      status === "Not authenticated" || status === 401
    ) {
      toast.error(
        "Tu sesión ha expirado. Por favor, inicia sesión nuevamente."
      );
      sessionStorage.clear();

      instance.logoutRedirect({
        onRedirectNavigate: () => false,
      });
    }
  };

  useEffect(() => {
    if (accounts.length) {
      const { name, username } = accounts[0];
      setUser({
        email: username ?? "",
        name: name ?? "",
        roles: ["Tester"],
      });
    } else setUser(null);
  }, [accounts]);

  return {
    logout,
    user,
  };
}
