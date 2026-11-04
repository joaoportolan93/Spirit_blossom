import axios from "axios";

/**
 * Lê o cookie csrftoken definido pelo Django.
 */
export function getCsrfTokenFromCookie() {
  if (typeof document === "undefined") return "";
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : "";
}

export const api = axios.create({
  baseURL: "",
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

// Interceptor para injetar X-CSRFToken em requisições mutativas
api.interceptors.request.use((config) => {
  const method = (config.method || "").toUpperCase();
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const csrfToken = getCsrfTokenFromCookie();
    if (csrfToken) {
      config.headers["X-CSRFToken"] = csrfToken;
    }
  }
  return config;
});

// Variáveis para controle de refresh único e concorrência
let refreshPromise = null;

// Interceptor de resposta: trata 401 com UMA única renovação e UMA tentativa após 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Se não há config ou já tentou renovar uma vez, rejeita direto
    if (!originalRequest || originalRequest._retry) {
      return Promise.reject(error);
    }

    const url = originalRequest.url || "";
    // Não tenta refresh para endpoints de autenticação
    if (
      url.includes("/api/auth/login/") ||
      url.includes("/api/auth/refresh/") ||
      url.includes("/api/auth/register/") ||
      url.includes("/api/auth/csrf/")
    ) {
      return Promise.reject(error);
    }

    if (error.response && error.response.status === 401) {
      originalRequest._retry = true;

      if (!refreshPromise) {
        refreshPromise = (async () => {
          try {
            await api.post("/api/auth/refresh/");
          } finally {
            refreshPromise = null;
          }
        })();
      }

      try {
        await refreshPromise;
        // Atualiza cabeçalho CSRF caso tenha sido rotacionado
        const csrfToken = getCsrfTokenFromCookie();
        if (csrfToken) {
          originalRequest.headers["X-CSRFToken"] = csrfToken;
        }
        return api(originalRequest);
      } catch (refreshError) {
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

/**
 * Chama /api/auth/csrf/ na inicialização do app para obter o cookie csrftoken.
 */
export async function initCsrf() {
  try {
    await api.get("/api/auth/csrf/");
  } catch {
    // Ignora falhas de rede inicial, o app tentará novamente nas requisições
  }
}
