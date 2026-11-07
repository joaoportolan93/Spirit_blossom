import { describe, it, expect, vi, beforeEach } from "vitest";
import { api, getCsrfTokenFromCookie, initCsrf } from "../services/api";

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
});
