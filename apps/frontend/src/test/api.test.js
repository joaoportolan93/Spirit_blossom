import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  api,
  getCsrfTokenFromCookie,
  initCsrf,
  getPostDetail,
  getPostComments,
  createComment,
  getCommentReplies,
  getCommentThread,
  getCommentDetail,
  editComment,
  deleteComment,
  toggleCommentLike,
  toggleCommentBookmark,
  getBookmarkedComments,
  editPost,
  deletePost,
  muteUser,
  unmuteUser,
  blockUser,
  unblockUser,
  hideComment,
  unhideComment,
  getPostHiddenComments,
} from "../services/api";

describe("API Service — CSRF & Interceptors", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    document.cookie = "csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
  });

  it("1. getCsrfTokenFromCookie extrai token do cookie document", () => {
    expect(getCsrfTokenFromCookie()).toBe("");

    document.cookie = "csrftoken=teste_token_12345; path=/";
    expect(getCsrfTokenFromCookie()).toBe("teste_token_12345");
  });

  it("2. Injeta X-CSRFToken em métodos mutantes (POST, PUT, PATCH, DELETE) e não em GET", () => {
    document.cookie = "csrftoken=my_csrf_secret; path=/";

    // Executa a função do interceptor de request diretamente
    const requestInterceptor = api.interceptors.request.handlers[0].fulfilled;

    const postConfig = requestInterceptor({ method: "post", headers: {} });
    expect(postConfig.headers["X-CSRFToken"]).toBe("my_csrf_secret");

    const putConfig = requestInterceptor({ method: "PUT", headers: {} });
    expect(putConfig.headers["X-CSRFToken"]).toBe("my_csrf_secret");

    const deleteConfig = requestInterceptor({ method: "DELETE", headers: {} });
    expect(deleteConfig.headers["X-CSRFToken"]).toBe("my_csrf_secret");

    const getConfig = requestInterceptor({ method: "get", headers: {} });
    expect(getConfig.headers["X-CSRFToken"]).toBeUndefined();
  });

  it("3. initCsrf chama /api/auth/csrf/ e trata erros de rede sem estourar exceção", async () => {
    const getSpy = vi.spyOn(api, "get").mockResolvedValueOnce({ data: { csrfToken: "abc" } });
    await expect(initCsrf()).resolves.toBeUndefined();
    expect(getSpy).toHaveBeenCalledWith("/api/auth/csrf/");

    // Falha silenciosa
    vi.spyOn(api, "get").mockRejectedValueOnce(new Error("Network failed"));
    await expect(initCsrf()).resolves.toBeUndefined();
  });

  it("4. Interceptor de resposta: rejeita direto se requisição já foi retentada (_retry=true, sem laço)", async () => {
    const responseErrorHandler = api.interceptors.response.handlers[0].rejected;

    const error = {
      config: { url: "/api/posts/", _retry: true },
      response: { status: 401 },
    };

    await expect(responseErrorHandler(error)).rejects.toBe(error);
  });

  it("5. Interceptor de resposta: não tenta refresh em rotas de autenticação", async () => {
    const responseErrorHandler = api.interceptors.response.handlers[0].rejected;

    const authUrls = [
      "/api/auth/login/",
      "/api/auth/refresh/",
      "/api/auth/register/",
      "/api/auth/csrf/",
    ];

    for (const url of authUrls) {
      const error = {
        config: { url, headers: {} },
        response: { status: 401 },
      };
      await expect(responseErrorHandler(error)).rejects.toBe(error);
    }
  });

  it("6. Trata 401 disparando refresh e retentando a requisição original com novo token CSRF via adapter mock", async () => {
    const responseErrorHandler = api.interceptors.response.handlers[0].rejected;

    document.cookie = "csrftoken=novo_csrf_token; path=/";

    const mockAdapter = vi.fn().mockImplementation(async (config) => {
      return {
        data: { ok: true },
        status: 200,
        statusText: "OK",
        headers: {},
        config,
      };
    });
    api.defaults.adapter = mockAdapter;

    const postSpy = vi.spyOn(api, "post").mockResolvedValueOnce({ data: { status: "refreshed" } });

    const originalRequest = {
      url: "/api/feed/",
      headers: {},
    };
    const error = {
      config: originalRequest,
      response: { status: 401 },
    };

    const result = await responseErrorHandler(error);

    expect(originalRequest._retry).toBe(true);
    expect(postSpy).toHaveBeenCalledWith("/api/auth/refresh/");
    expect(originalRequest.headers["X-CSRFToken"]).toBe("novo_csrf_token");
    expect(result.data).toEqual({ ok: true });
  });

  it("7. Interceptor de resposta: rejeita com erro original quando o refresh falha (linhas 79-80 de api.js)", async () => {
    const responseErrorHandler = api.interceptors.response.handlers[0].rejected;

    const refreshFailure = new Error("Sessão expirada");
    vi.spyOn(api, "post").mockRejectedValueOnce(refreshFailure);

    const error = {
      config: { url: "/api/posts/", headers: {} },
      response: { status: 401 },
    };

    await expect(responseErrorHandler(error)).rejects.toBe(refreshFailure);
  });

  it("8. Interceptor de resposta: rejeita diretamente erros sem response ou não-401 (linhas 82-83 de api.js)", async () => {
    const responseErrorHandler = api.interceptors.response.handlers[0].rejected;

    const error500 = {
      config: { url: "/api/feed/", headers: {} },
      response: { status: 500 },
    };
    await expect(responseErrorHandler(error500)).rejects.toBe(error500);

    const errorSemResponse = {
      config: { url: "/api/feed/", headers: {} },
    };
    await expect(responseErrorHandler(errorSemResponse)).rejects.toBe(errorSemResponse);
  });

  describe("API de Comentários (Onda 4 / ADR-N24)", () => {
    it("getPostDetail faz GET no post por ID", async () => {
      const spy = vi.spyOn(api, "get").mockResolvedValueOnce({ data: { id: "p-1" } });
      const res = await getPostDetail("p-1");
      expect(spy).toHaveBeenCalledWith("/api/posts/p-1/");
      expect(res).toEqual({ id: "p-1" });
    });

    it("getPostComments faz GET com sort e cursor opcionais", async () => {
      const spy = vi.spyOn(api, "get").mockResolvedValueOnce({ data: { items: [] } });
      await getPostComments("p-1", "likes", "cur_abc");
      expect(spy).toHaveBeenCalledWith("/api/posts/p-1/comments/?sort=likes&cursor=cur_abc");
    });

    it("createComment faz POST para novo comentário", async () => {
      const spy = vi.spyOn(api, "post").mockResolvedValueOnce({ data: { id: "c-new" } });
      const res = await createComment("p-1", { content_text: "Olá", parent_id: "c-root" });
      expect(spy).toHaveBeenCalledWith("/api/posts/p-1/comments/", {
        content_text: "Olá",
        parent_id: "c-root",
      });
      expect(res).toEqual({ id: "c-new" });
    });

    it("getCommentReplies faz GET nas respostas com sort e cursor", async () => {
      const spy = vi.spyOn(api, "get").mockResolvedValueOnce({ data: { items: [] } });
      await getCommentReplies("c-1", "recent", "cur_123");
      expect(spy).toHaveBeenCalledWith("/api/comments/c-1/replies/?sort=recent&cursor=cur_123");
    });

    it("getCommentThread faz GET no contexto de Focar", async () => {
      const spy = vi.spyOn(api, "get").mockResolvedValueOnce({ data: { ancestors: [] } });
      const res = await getCommentThread("c-1");
      expect(spy).toHaveBeenCalledWith("/api/comments/c-1/thread/");
      expect(res).toEqual({ ancestors: [] });
    });

    it("getCommentDetail faz GET em comentário específico", async () => {
      const spy = vi.spyOn(api, "get").mockResolvedValueOnce({ data: { id: "c-1" } });
      const res = await getCommentDetail("c-1");
      expect(spy).toHaveBeenCalledWith("/api/comments/c-1/");
      expect(res).toEqual({ id: "c-1" });
    });

    it("editComment faz PATCH no texto do comentário", async () => {
      const spy = vi.spyOn(api, "patch").mockResolvedValueOnce({ data: { content_text: "Novo" } });
      const res = await editComment("c-1", "Novo");
      expect(spy).toHaveBeenCalledWith("/api/comments/c-1/", { content_text: "Novo" });
      expect(res).toEqual({ content_text: "Novo" });
    });

    it("deleteComment faz DELETE no comentário", async () => {
      const spy = vi.spyOn(api, "delete").mockResolvedValueOnce({ data: {} });
      await deleteComment("c-1");
      expect(spy).toHaveBeenCalledWith("/api/comments/c-1/");
    });

    it("toggleCommentLike faz POST no like do comentário", async () => {
      const spy = vi.spyOn(api, "post").mockResolvedValueOnce({ data: { is_liked: true } });
      const res = await toggleCommentLike("c-1");
      expect(spy).toHaveBeenCalledWith("/api/comments/c-1/like/");
      expect(res).toEqual({ is_liked: true });
    });

    it("toggleCommentBookmark faz POST no bookmark do comentário", async () => {
      const spy = vi.spyOn(api, "post").mockResolvedValueOnce({ data: { is_bookmarked: true } });
      const res = await toggleCommentBookmark("c-1");
      expect(spy).toHaveBeenCalledWith("/api/comments/c-1/bookmark/");
      expect(res).toEqual({ is_bookmarked: true });
    });

    it("getBookmarkedComments faz GET nos comentários salvos", async () => {
      const spy = vi.spyOn(api, "get").mockResolvedValueOnce({ data: { items: [] } });
      const res = await getBookmarkedComments();
      expect(spy).toHaveBeenCalledWith("/api/comments/bookmarks/");
      expect(res).toEqual({ items: [] });
    });

    it("editPost e deletePost chamam endpoints corretos", async () => {
      const patchSpy = vi.spyOn(api, "patch").mockResolvedValueOnce({ data: { id: "p-1" } });
      await editPost("p-1", "editado");
      expect(patchSpy).toHaveBeenCalledWith("/api/posts/p-1/", { content_text: "editado" });

      const delSpy = vi.spyOn(api, "delete").mockResolvedValueOnce({ data: {} });
      await deletePost("p-1");
      expect(delSpy).toHaveBeenCalledWith("/api/posts/p-1/");
    });

    it("muteUser, unmuteUser, blockUser e unblockUser chamam endpoints de social", async () => {
      const postSpy = vi.spyOn(api, "post").mockResolvedValue({ data: {} });
      const delSpy = vi.spyOn(api, "delete").mockResolvedValue({ data: {} });

      await muteUser("bob");
      expect(postSpy).toHaveBeenCalledWith("/api/social/mute/bob/");

      await unmuteUser("bob");
      expect(delSpy).toHaveBeenCalledWith("/api/social/mute/bob/");

      await blockUser("bob");
      expect(postSpy).toHaveBeenCalledWith("/api/social/block/bob/");

      await unblockUser("bob");
      expect(delSpy).toHaveBeenCalledWith("/api/social/block/bob/");
    });

    it("hideComment, unhideComment e getPostHiddenComments chamam endpoints de moderação", async () => {
      const postSpy = vi.spyOn(api, "post").mockResolvedValueOnce({ data: {} });
      await hideComment("c-1");
      expect(postSpy).toHaveBeenCalledWith("/api/comments/c-1/hide/");

      const delSpy = vi.spyOn(api, "delete").mockResolvedValueOnce({ data: {} });
      await unhideComment("c-1");
      expect(delSpy).toHaveBeenCalledWith("/api/comments/c-1/hide/");

      const getSpy = vi.spyOn(api, "get").mockResolvedValueOnce({ data: { items: [] } });
      await getPostHiddenComments("p-1", "cursor-xyz");
      expect(getSpy).toHaveBeenCalledWith("/api/posts/p-1/hidden-comments/?cursor=cursor-xyz");
    });
  });
});
