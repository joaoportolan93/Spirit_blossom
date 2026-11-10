import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { NotificationBell } from "../components/NotificationBell";
import { api } from "../services/api";
import "../i18n";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe("NotificationBell Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. Renderiza o sino sem badge quando não há pedidos pendentes", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({ data: { results: [] } });

    render(
      <MemoryRouter>
        <NotificationBell />
      </MemoryRouter>
    );

    const bellBtn = screen.getByTestId("notification-bell-btn");
    expect(bellBtn).toBeInTheDocument();
    expect(screen.queryByTestId("unread-badge")).not.toBeInTheDocument();
  });

  it("2. Renderiza badge com a contagem quando há pedidos pendentes", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: { results: [{ id: "1" }, { id: "2" }, { id: "3" }] },
    });

    render(
      <MemoryRouter>
        <NotificationBell />
      </MemoryRouter>
    );

    await waitFor(() => {
      const badge = screen.getByTestId("unread-badge");
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveTextContent("3");
    });
  });

  it("3. Navega para /notifications ao clicar no botão", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({ data: { results: [] } });

    render(
      <MemoryRouter>
        <NotificationBell />
      </MemoryRouter>
    );

    const bellBtn = screen.getByTestId("notification-bell-btn");
    fireEvent.click(bellBtn);

    expect(mockNavigate).toHaveBeenCalledWith("/notifications");
  });

  it("4. Trata erro silenciosamente sem falhar o componente", async () => {
    vi.spyOn(api, "get").mockRejectedValueOnce(new Error("Network error"));

    render(
      <MemoryRouter>
        <NotificationBell />
      </MemoryRouter>
    );

    expect(screen.getByTestId("notification-bell-btn")).toBeInTheDocument();
  });
});

