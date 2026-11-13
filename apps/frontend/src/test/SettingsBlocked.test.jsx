import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { SettingsBlocked } from "../pages/settings/SettingsBlocked";
import { api } from "../services/api";
import "../i18n";

describe("SettingsBlocked Component (Onda 4c / ADR-N24)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. Renderiza estado vazio quando não há usuários bloqueados", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: { items: [] },
    });

    render(<SettingsBlocked />);

    expect(screen.getByText("Carregando...")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId("empty-blocked-list")).toBeInTheDocument();
      expect(screen.getByText("Nenhuma conta bloqueada.")).toBeInTheDocument();
    });
  });

  it("2. Lista usuários bloqueados com botão Desbloquear", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: {
        items: [
          { id: "1", username: "usuario_bloqueado_1", avatar: null, blocked_at: "2026-11-10T12:00:00Z" },
          { id: "2", username: "usuario_bloqueado_2", avatar: "http://avatar.jpg", blocked_at: "2026-11-09T10:00:00Z" },
        ],
      },
    });

    render(<SettingsBlocked />);

    await waitFor(() => {
      expect(screen.getByText("@usuario_bloqueado_1")).toBeInTheDocument();
      expect(screen.getByText("@usuario_bloqueado_2")).toBeInTheDocument();
      expect(screen.getByTestId("unblock-btn-usuario_bloqueado_1")).toBeInTheDocument();
      expect(screen.getByTestId("unblock-btn-usuario_bloqueado_2")).toBeInTheDocument();
    });
  });

  it("3. Desbloqueia usuário e permite Desfazer (Undo)", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: {
        items: [{ id: "1", username: "bloqueado_teste", avatar: null }],
      },
    });
    vi.spyOn(api, "delete").mockResolvedValueOnce({});
    vi.spyOn(api, "post").mockResolvedValueOnce({});

    render(<SettingsBlocked />);

    await waitFor(() => {
      expect(screen.getByText("@bloqueado_teste")).toBeInTheDocument();
    });

    // Clica em Desbloquear
    const unblockBtn = screen.getByTestId("unblock-btn-bloqueado_teste");
    fireEvent.click(unblockBtn);

    await waitFor(() => {
      expect(api.delete).toHaveBeenCalledWith("/api/social/block/bloqueado_teste/");
      expect(screen.getByText(/@bloqueado_teste foi desbloqueado/)).toBeInTheDocument();
      expect(screen.getByTestId("undo-unblock-btn")).toBeInTheDocument();
    });

    // Clica em Desfazer
    const undoBtn = screen.getByTestId("undo-unblock-btn");
    fireEvent.click(undoBtn);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/social/block/bloqueado_teste/");
      expect(screen.getByText("Ação desfeita.")).toBeInTheDocument();
      expect(screen.getByText("@bloqueado_teste")).toBeInTheDocument();
    });
  });

  it("4. Trata erro ao carregar lista de bloqueados", async () => {
    vi.spyOn(api, "get").mockRejectedValueOnce(new Error("Network Error"));

    render(<SettingsBlocked />);

    await waitFor(() => {
      expect(screen.getByText("Algo deu errado. Tente novamente.")).toBeInTheDocument();
    });
  });

  it("5. Trata erro ao desbloquear e erro ao desfazer", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: {
        items: [{ id: "1", username: "usuario_falha", avatar: null }],
      },
    });
    vi.spyOn(api, "delete").mockRejectedValueOnce(new Error("Erro ao desbloquear"));

    render(<SettingsBlocked />);

    await waitFor(() => {
      expect(screen.getByText("@usuario_falha")).toBeInTheDocument();
    });

    // Erro ao desbloquear
    fireEvent.click(screen.getByTestId("unblock-btn-usuario_falha"));
    await waitFor(() => {
      expect(screen.getByText("Algo deu errado. Tente novamente.")).toBeInTheDocument();
    });

    // Desbloqueia com sucesso e falha ao desfazer
    vi.spyOn(api, "delete").mockResolvedValueOnce({});
    vi.spyOn(api, "post").mockRejectedValueOnce(new Error("Erro ao desfazer"));

    fireEvent.click(screen.getByTestId("unblock-btn-usuario_falha"));
    await waitFor(() => {
      expect(screen.getByTestId("undo-unblock-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("undo-unblock-btn"));
    await waitFor(() => {
      expect(screen.getByText("Algo deu errado. Tente novamente.")).toBeInTheDocument();
    });
  });
});

