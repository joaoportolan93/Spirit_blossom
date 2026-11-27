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
  if (typeof FormData !== "undefined" && config.data instanceof FormData && config.headers) {
    delete config.headers["Content-Type"];
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

export async function editPost(postId, payload) {
  const body = typeof payload === "string" ? { content_text: payload } : payload;
  const res = await api.patch(`/api/posts/${postId}/`, body);
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

export async function createComment(postId, payload) {
  if (typeof FormData !== "undefined" && payload instanceof FormData) {
    const res = await api.post(`/api/posts/${postId}/comments/`, payload);
    return res.data;
  }
  const { content_text = "", parent_id = null, image = null, video = null } = payload || {};
  if (image || video) {
    const formData = new FormData();
    if (content_text) formData.append("content_text", content_text);
    if (parent_id) formData.append("parent_id", parent_id);
    if (image) formData.append("image", image);
    if (video) formData.append("video", video);
    const res = await api.post(`/api/posts/${postId}/comments/`, formData);
    return res.data;
  }
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

export async function deleteAccount(payload) {
  // payload: { current_password } para contas com senha
  //          { confirm_username } para contas Google OAuth
  const res = await api.delete("/api/users/account/", { data: payload });
  return res.data;
}

export async function getUserSettings() {
  const res = await api.get("/api/users/settings/");
  return res.data;
}

export async function updateUserSettings(data) {
  const headers = data instanceof FormData ? { "Content-Type": "multipart/form-data" } : {};
  const res = await api.patch("/api/users/settings/", data, { headers });
  return res.data;
}

export async function changePassword({ current_password, new_password, new_password_confirm }) {
  const res = await api.post("/api/auth/change-password/", {
    current_password,
    new_password,
    new_password_confirm,
  });
  return res.data;
}

export async function getCurrentUser() {
  const res = await api.get("/api/auth/me/");
  return res.data;
}

export async function getProfileLikes(username) {
  const res = await api.get(`/api/social/profile/${username}/likes/`);
  return res.data;
}

// ----------------------------------------------------------------------------
// API de Notificações — Onda 7a
// ----------------------------------------------------------------------------

export async function getNotifications({ category = "all", unreadOnly = false } = {}) {
  const params = new URLSearchParams();
  if (category && category !== "all") params.append("category", category);
  if (unreadOnly) params.append("unread_only", "true");
  const qs = params.toString() ? `?${params.toString()}` : "";
  const res = await api.get(`/api/notifications/${qs}`);
  return res.data;
}

export async function getUnreadCount() {
  const res = await api.get("/api/notifications/unread-count/");
  return res.data?.unread_count ?? 0;
}

export async function markNotificationRead(id) {
  const res = await api.post(`/api/notifications/${id}/read/`);
  return res.data;
}

export async function markAllNotificationsRead() {
  const res = await api.post("/api/notifications/mark-all-read/");
  return res.data;
}

export async function registerPushDevice({ token, platform = "web", device_name = "" }) {
  const res = await api.post("/api/notifications/devices/", { token, platform, device_name });
  return res.data;
}

export async function removePushDevice(token) {
  const res = await api.delete("/api/notifications/devices/", { data: { token } });
  return res.data;
}

export async function getFeatureFlags() {
  const res = await api.get("/api/feature-flags/");
  return res.data?.flags ?? {};
}

// ----------------------------------------------------------------------------
// API de Descoberta, Menções e Hashtags — Onda 7b
// ----------------------------------------------------------------------------

export async function searchUsers(query, limit = 5) {
  const res = await api.get(
    `/api/users/search/?q=${encodeURIComponent(query)}&limit=${limit}`
  );
  return res.data?.results || [];
}

export async function getFollowSuggestions(limit = 5) {
  const res = await api.get(`/api/social/suggestions/?limit=${limit}`);
  return res.data?.results || [];
}

export async function getTrendingHashtags(limit = 8) {
  const res = await api.get(`/api/hashtags/trending/?limit=${limit}`);
  return res.data?.results || [];
}

// ----------------------------------------------------------------------------
// API de Denúncias, Moderação e Painel Admin — Onda 8
// ----------------------------------------------------------------------------

export async function createReport({ target_type, target_id, reason, description = "" }) {
  const res = await api.post("/api/reports/", {
    target_type,
    target_id,
    reason,
    description,
  });
  return res.data;
}

export async function getAdminStats() {
  const res = await api.get("/api/admin/stats/");
  return res.data;
}

export async function getAdminUsers({ search = "", status = "", page = 1 } = {}) {
  const params = new URLSearchParams();
  if (search) params.set("search", search);
  if (status) params.set("status", status);
  params.set("page", String(page));
  const res = await api.get(`/api/admin/users/?${params.toString()}`);
  return res.data;
}

export async function getAdminUserDetail(userId) {
  const res = await api.get(`/api/admin/users/${userId}/`);
  return res.data;
}

export async function updateAdminUserStatus(userId, payload) {
  const res = await api.patch(`/api/admin/users/${userId}/`, payload);
  return res.data;
}

export async function permanentlyDeleteAdminUser(userId, confirmUsername) {
  const res = await api.delete(`/api/admin/users/${userId}/`, {
    data: { confirm_username: confirmUsername },
  });
  return res.data;
}

export async function getAdminReports({ status = "pending", target_type = "all" } = {}) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (target_type && target_type !== "all") params.set("target_type", target_type);
  const res = await api.get(`/api/admin/reports/?${params.toString()}`);
  return res.data;
}

export async function executeReportAction(reportId, payload) {
  const res = await api.post(`/api/admin/reports/${reportId}/action/`, payload);
  return res.data;
}

export async function getAdminModerationLogs() {
  const res = await api.get("/api/admin/moderation-logs/");
  return res.data;
}

export async function getAdminFeatureFlags() {
  const res = await api.get("/api/admin/feature-flags/");
  return res.data;
}

export async function createAdminFeatureFlag(payload) {
  const res = await api.post("/api/admin/feature-flags/", payload);
  return res.data;
}

export async function updateAdminFeatureFlag(key, payload) {
  const res = await api.patch(`/api/admin/feature-flags/${key}/`, payload);
  return res.data;
}

export async function deleteAdminFeatureFlag(key) {
  const res = await api.delete(`/api/admin/feature-flags/${key}/`);
  return res.data;
}

