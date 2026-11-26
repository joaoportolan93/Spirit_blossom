import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Navbar } from "../components/Navbar";
import { AuthContext } from "../hooks/useAuth";
import * as apiModule from "../services/api";
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

  it("1. Renderiza links para usuário autenticado incluindo configurações e perfil", () => {
    renderNavbar({ username: "alice" });

    expect(screen.getByText("Feed")).toBeInTheDocument();
    expect(screen.getByText("Explorar")).toBeInTheDocument();
    expect(screen.getByText("Buscar")).toBeInTheDocument();
    expect(screen.getByText("Salvos")).toBeInTheDocument();
    expect(screen.getByText("Configurações")).toBeInTheDocument();
    expect(screen.getByText("Perfil")).toBeInTheDocument();
    expect(screen.queryByText("Círculo")).not.toBeInTheDocument();
    expect(screen.queryByText("Pedidos")).not.toBeInTheDocument();
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

  it("4. Exibe bolinha e contador de notificações não lidas e atualiza via evento", async () => {
    const spy = vi
      .spyOn(apiModule, "getUnreadCount")
      .mockResolvedValueOnce(14)
      .mockResolvedValueOnce(0);

    renderNavbar({ username: "alice" });

    await waitFor(() => {
      expect(screen.getByTestId("nav-notif-dot")).toBeInTheDocument();
      expect(screen.getByTestId("nav-notif-badge")).toHaveTextContent("14");
    });

    await act(async () => {
      window.dispatchEvent(new Event("spirit-notifications-updated"));
    });

    await waitFor(() => {
      expect(spy).toHaveBeenCalledTimes(2);
      expect(screen.queryByTestId("nav-notif-badge")).not.toBeInTheDocument();
      expect(screen.queryByTestId("nav-notif-dot")).not.toBeInTheDocument();
    });
  });
});

