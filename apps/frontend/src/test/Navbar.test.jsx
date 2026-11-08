import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Navbar } from "../components/Navbar";
import { AuthContext } from "../hooks/useAuth";
import "../i18n";

vi.mock("../components/NotificationBell", () => ({
  NotificationBell: () => <div data-testid="mock-notification-bell" />,
}));

function renderNavbar(user = null, logout = vi.fn()) {
  const authValue = {
    user,
    loading: false,
    login: vi.fn(),
    logout,
  };

  return render(
    <AuthContext.Provider value={authValue}>
      <MemoryRouter>
        <Navbar />
      </MemoryRouter>
    </AuthContext.Provider>
  );
}

describe("Navbar Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. Renderiza links para usuário autenticado incluindo pedidos e perfil", () => {
    renderNavbar({ username: "alice" });

    expect(screen.getByText("Feed")).toBeInTheDocument();
    expect(screen.getByText("Explorar")).toBeInTheDocument();
    expect(screen.getByText("Buscar")).toBeInTheDocument();
    expect(screen.getByText("Círculo")).toBeInTheDocument();
    expect(screen.getByText("Salvos")).toBeInTheDocument();
    expect(screen.getByText("Pedidos")).toBeInTheDocument();
    expect(screen.getByText("Perfil")).toBeInTheDocument();
    expect(screen.getByText("Sair")).toBeInTheDocument();
    expect(screen.getByTestId("mock-notification-bell")).toBeInTheDocument();
  });

  it("2. Executa logout ao clicar no botão sair", async () => {
    const mockLogout = vi.fn().mockResolvedValue();
    renderNavbar({ username: "alice" }, mockLogout);

    const logoutBtn = screen.getByText("Sair");
    fireEvent.click(logoutBtn);

    await waitFor(() => {
      expect(mockLogout).toHaveBeenCalledTimes(1);
    });
  });

  it("3. Renderiza botões de Entrar e Cadastrar para visitante anônimo", () => {
    renderNavbar(null);

    expect(screen.getByText("Entrar")).toBeInTheDocument();
    expect(screen.getByText("Criar conta (18+)")).toBeInTheDocument();
    expect(screen.queryByText("Pedidos")).not.toBeInTheDocument();
  });
});

