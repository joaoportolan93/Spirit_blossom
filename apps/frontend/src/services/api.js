import axios from "axios";
import i18n from "../i18n";

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

// Interceptor para injetar X-CSRFToken em requisições mutativas e Accept-Language com idioma atual
api.interceptors.request.use((config) => {
  if (i18n && i18n.language) {
    config.headers["Accept-Language"] = i18n.language;
  }
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


// ----------------------------------------------------------------------------
// API de Comentários (Onda 4 / ADR-N24)
// ----------------------------------------------------------------------------

export async function getPostDetail(postId) {
  const res = await api.get(`/api/posts/${postId}/`);
  return res.data;
}

export async function editPost(postId, content_text) {
  const res = await api.patch(`/api/posts/${postId}/`, { content_text });
  return res.data;
}

export async function deletePost(postId) {
  const res = await api.delete(`/api/posts/${postId}/`);
  return res.data;
}

export async function muteUser(username) {
  const res = await api.post(`/api/social/mute/${username}/`);
  return res.data;
}

export async function unmuteUser(username) {
  const res = await api.delete(`/api/social/mute/${username}/`);
  return res.data;
}

export async function blockUser(username) {
  const res = await api.post(`/api/social/block/${username}/`);
  return res.data;
}

export async function unblockUser(username) {
  const res = await api.delete(`/api/social/block/${username}/`);
  return res.data;
}

export async function hideComment(commentId) {
  const res = await api.post(`/api/comments/${commentId}/hide/`);
  return res.data;
}

export async function unhideComment(commentId) {
  const res = await api.delete(`/api/comments/${commentId}/hide/`);
  return res.data;
}

export async function getPostHiddenComments(postId, cursor = null) {
  const params = new URLSearchParams();
  if (cursor) params.append("cursor", cursor);
  const queryString = params.toString() ? `?${params.toString()}` : "";
  const res = await api.get(`/api/posts/${postId}/hidden-comments/${queryString}`);
  return res.data;
}

export async function getPostComments(postId, sort = "recent", cursor = null) {
  const params = new URLSearchParams({ sort });
  if (cursor) params.append("cursor", cursor);
  const res = await api.get(`/api/posts/${postId}/comments/?${params.toString()}`);
  return res.data;
}

export async function createComment(postId, { content_text, parent_id = null }) {
  const res = await api.post(`/api/posts/${postId}/comments/`, {
    content_text,
    parent_id,
  });
  return res.data;
}

export async function getCommentReplies(commentId, sort = "recent", cursor = null) {
  const params = new URLSearchParams({ sort });
  if (cursor) params.append("cursor", cursor);
  const res = await api.get(`/api/comments/${commentId}/replies/?${params.toString()}`);
  return res.data;
}

export async function getCommentThread(commentId) {
  const res = await api.get(`/api/comments/${commentId}/thread/`);
  return res.data;
}

export async function getCommentDetail(commentId) {
  const res = await api.get(`/api/comments/${commentId}/`);
  return res.data;
}

export async function editComment(commentId, content_text) {
  const res = await api.patch(`/api/comments/${commentId}/`, { content_text });
  return res.data;
}

export async function deleteComment(commentId) {
  const res = await api.delete(`/api/comments/${commentId}/`);
  return res.data;
}

export async function toggleCommentLike(commentId) {
  const res = await api.post(`/api/comments/${commentId}/like/`);
  return res.data;
}

export async function toggleCommentBookmark(commentId) {
  const res = await api.post(`/api/comments/${commentId}/bookmark/`);
  return res.data;
}

export async function getBookmarkedComments() {
  const res = await api.get("/api/comments/bookmarks/");
  return res.data;
}

export async function getBlockedUsers() {
  const res = await api.get("/api/social/blocked-users/");
  return res.data?.items || [];
}

export async function getMutedUsers() {
  const res = await api.get("/api/social/muted-users/");
  return res.data?.items || [];
}

export async function exportUserData() {
  const res = await api.get("/api/users/export-data/");
  return res.data;
}
