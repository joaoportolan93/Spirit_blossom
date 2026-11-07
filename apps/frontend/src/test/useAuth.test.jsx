import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { AuthProvider, useAuth } from "../hooks/useAuth";
import { api } from "../services/api";

function TestConsumer() {
  const { user, loading, login, register, logout } = useAuth();

  return (
    <div>
      <div data-testid="loading">{loading ? "loading" : "idle"}</div>
      <div data-testid="user">{user ? user.email || user.username || "authenticated" : "guest"}</div>
      <button
        onClick={() => login("test@example.com", "pass123")}
        data-testid="login-btn"
      >
        Login
      </button>
      <button
        onClick={() =>
          register({
            email: "new@example.com",
            username: "newuser",
            password: "p1",
            password_confirm: "p1",
            birth_date: "1995-01-01",
          })
        }
        data-testid="register-btn"
      >
        Register
      </button>
      <button onClick={() => logout()} data-testid="logout-btn">
        Logout
      </button>
    </div>
  );
}

describe("useAuth Hook & AuthProvider", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("1. useAuth lança erro se renderizado fora do AuthProvider", () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    function InvalidComponent() {
      useAuth();
      return null;
    }

    expect(() => render(<InvalidComponent />)).toThrow(
      "useAuth deve ser utilizado dentro de um AuthProvider"
    );

    consoleSpy.mockRestore();
  });

  it("2. Inicialização: usuário autenticado quando /api/notifications/ retorna 200", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/notifications/")) {
        return Promise.resolve({ status: 200, data: [] });
      }
      return Promise.resolve({ status: 200, data: {} });
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    expect(screen.getByTestId("loading")).toHaveTextContent("loading");

    await waitFor(() => {
      expect(screen.getByTestId("loading")).toHaveTextContent("idle");
      expect(screen.getByTestId("user")).toHaveTextContent("authenticated");
    });
  });

  it("3. Inicialização: visitante anônimo quando /api/notifications/ falha com 401", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/notifications/")) {
        return Promise.reject(new Error("Unauthorized"));
      }
      return Promise.resolve({ status: 200, data: {} });
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading")).toHaveTextContent("idle");
      expect(screen.getByTestId("user")).toHaveTextContent("guest");
    });
  });

  it("4. Operações de login e logout atualizam o estado do usuário", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/notifications/")) {
        return Promise.reject(new Error("Unauthorized"));
      }
      return Promise.resolve({ status: 200, data: {} });
    });
    vi.spyOn(api, "post").mockImplementation((url) => {
      if (url.includes("/api/auth/login/")) {
        return Promise.resolve({ data: { detail: "Login com sucesso" } });
      }
      if (url.includes("/api/auth/logout/")) {
        return Promise.resolve({ data: {} });
      }
      return Promise.resolve({ data: {} });
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId("loading")).toHaveTextContent("idle"));

    // Executa Login
    await act(async () => {
      screen.getByTestId("login-btn").click();
    });

    await waitFor(() => {
      expect(screen.getByTestId("user")).toHaveTextContent("test@example.com");
    });

    // Executa Logout
    await act(async () => {
      screen.getByTestId("logout-btn").click();
    });

    await waitFor(() => {
      expect(screen.getByTestId("user")).toHaveTextContent("guest");
    });
  });

  it("5. Operação de registro atualiza o estado com dados cadastrados", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/notifications/")) {
        return Promise.reject(new Error("Unauthorized"));
      }
      return Promise.resolve({ status: 200, data: {} });
    });
    vi.spyOn(api, "post").mockResolvedValueOnce({
      data: { email: "new@example.com", username: "newuser" },
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId("loading")).toHaveTextContent("idle"));

    await act(async () => {
      screen.getByTestId("register-btn").click();
    });

    await waitFor(() => {
      expect(screen.getByTestId("user")).toHaveTextContent("new@example.com");
    });
  });
});
