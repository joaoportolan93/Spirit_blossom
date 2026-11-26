import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Login } from "../pages/Login";
import * as authHook from "../hooks/useAuth";
import { api } from "../services/api";
import "../i18n";

describe("LoginForm Component (3 testes)", () => {
  const mockLogin = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(authHook, "useAuth").mockReturnValue({
      user: null,
      loading: false,
      login: mockLogin,
      register: vi.fn(),
      logout: vi.fn(),
    });
  });

  it("1. Renderiza campos de email, senha e botão de entrar", () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    expect(screen.getByTestId("email-input")).toBeInTheDocument();
    expect(screen.getByTestId("password-input")).toBeInTheDocument();
    expect(screen.getByTestId("login-submit")).toBeInTheDocument();
  });

  it("2. Exibe erro ao tentar submeter com campos vazios", async () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    fireEvent.submit(screen.getByTestId("login-form"));

    expect(mockLogin).not.toHaveBeenCalled();
  });

  it("3. Exibe mensagem de erro da API quando o login falha", async () => {
    mockLogin.mockRejectedValueOnce({
      response: {
        status: 400,
        data: { detail: "Credenciais inválidas." },
      },
    });

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByTestId("email-input"), {
      target: { value: "user@example.com" },
    });
    fireEvent.change(screen.getByTestId("password-input"), {
      target: { value: "errada123" },
    });

    fireEvent.submit(screen.getByTestId("login-form"));

    await waitFor(() => {
      expect(screen.getByTestId("login-error")).toBeInTheDocument();
      expect(screen.getByTestId("login-error")).toHaveTextContent("Credenciais inválidas.");
    });
  });

  it("4. Exibe card de conta banida com motivo e link mailto para moderação", async () => {
    mockLogin.mockRejectedValueOnce({
      response: {
        status: 400,
        data: {
          detail: "Credenciais inválidas ou conta inativa.",
          banned: true,
          ban_reason: "Violação das diretrizes",
          appeal_days_remaining: 29,
          appeal_email: "moderacao@spirit.blossom",
        },
      },
    });

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByTestId("email-input"), {
      target: { value: "banido@example.com" },
    });
    fireEvent.change(screen.getByTestId("password-input"), {
      target: { value: "senhaforte123" },
    });

    fireEvent.submit(screen.getByTestId("login-form"));

    await waitFor(() => {
      expect(screen.getByTestId("banned-account-card")).toBeInTheDocument();
      expect(screen.getByTestId("banned-reason-text")).toHaveTextContent(
        "Violação das diretrizes"
      );
      const appealLink = screen.getByTestId("banned-appeal-link");
      expect(appealLink).toHaveAttribute(
        "href",
        expect.stringContaining("mailto:moderacao@spirit.blossom")
      );
    });

    fireEvent.click(screen.getByTestId("banned-back-button"));
    expect(screen.getByTestId("login-form")).toBeInTheDocument();
  });

  it("5. Exibe expiração em suspensão temporária e trata banimento via Google OAuth", async () => {
    const postSpy = vi.spyOn(api, "post").mockRejectedValueOnce({
      response: {
        status: 403,
        data: {
          banned: true,
          ban_reason: "",
          ban_expires_at: "2026-12-01T12:00:00Z",
        },
      },
    });
    window.__GOOGLE_TEST_TOKEN__ = "mock-token";

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByTestId("google-login-button"));

    await waitFor(() => {
      expect(screen.getByTestId("banned-account-card")).toBeInTheDocument();
      expect(screen.getByTestId("banned-reason-text")).toHaveTextContent(
        "Violação das regras da comunidade."
      );
      expect(screen.getByTestId("banned-appeal-link")).toHaveAttribute(
        "href",
        expect.stringContaining("mailto:moderacao@spirit.blossom")
      );
    });

    delete window.__GOOGLE_TEST_TOKEN__;
    postSpy.mockRestore();
  });

  it("6. Exibe erro de throttle (429) e erro genérico no Google login", async () => {
    mockLogin.mockRejectedValueOnce({
      response: { status: 429, data: {} },
    });

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByTestId("email-input"), {
      target: { value: "user@example.com" },
    });
    fireEvent.change(screen.getByTestId("password-input"), {
      target: { value: "pass123" },
    });
    fireEvent.submit(screen.getByTestId("login-form"));

    await waitFor(() => {
      expect(screen.getByTestId("login-error")).toBeInTheDocument();
    });

    const postSpy = vi.spyOn(api, "post").mockRejectedValueOnce(new Error("network"));
    window.__GOOGLE_TEST_TOKEN__ = "bad-token";
    fireEvent.click(screen.getByTestId("google-login-button"));

    await waitFor(() => {
      expect(screen.getByTestId("login-error")).toHaveTextContent("Falha na autenticação com Google");
    });

    delete window.__GOOGLE_TEST_TOKEN__;
    postSpy.mockRestore();
  });
});
