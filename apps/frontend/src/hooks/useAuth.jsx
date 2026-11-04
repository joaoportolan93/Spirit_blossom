import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { api, initCsrf } from "../services/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Verifica estado de autenticação na inicialização sem depender de storage
  useEffect(() => {
    let isMounted = true;

    async function checkAuth() {
      await initCsrf();
      try {
        // Testa se o cookie de acesso/refresh é válido buscando notificações ou feed
        const res = await api.get("/api/notifications/");
        if (isMounted && res.status === 200) {
          // Usuário autenticado
          setUser((prev) => prev || { is_authenticated: true });
        }
      } catch {
        if (isMounted) {
          setUser(null);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    checkAuth();
    return () => {
      isMounted = false;
    };
  }, []);

  const login = useCallback(async (email, password) => {
    const response = await api.post("/api/auth/login/", { email, password });
    setUser({ email, is_authenticated: true });
    return response.data;
  }, []);

  const register = useCallback(
    async ({ email, username, password, password_confirm, birth_date }) => {
      const response = await api.post("/api/auth/register/", {
        email,
        username,
        password,
        password_confirm,
        birth_date,
      });
      setUser({ email, username, birth_date, is_authenticated: true });
      return response.data;
    },
    []
  );

  const logout = useCallback(async () => {
    try {
      await api.post("/api/auth/logout/");
    } catch {
      // Ignora erro no logout para limpar estado local
    } finally {
      setUser(null);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, setUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth deve ser utilizado dentro de um AuthProvider");
  }
  return context;
}
