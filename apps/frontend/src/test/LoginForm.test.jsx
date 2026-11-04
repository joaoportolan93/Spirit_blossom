import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Login } from "../pages/Login";
import * as authHook from "../hooks/useAuth";
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
});
