import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { SettingsMuted } from "../pages/settings/SettingsMuted";
import { api } from "../services/api";
import "../i18n";

describe("SettingsMuted Component (Onda 4c / ADR-N24)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. Renderiza estado vazio quando não há usuários silenciados", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: { items: [] },
    });

    render(<SettingsMuted />);

    expect(screen.getByText("Carregando...")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId("empty-muted-list")).toBeInTheDocument();
      expect(screen.getByText("Nenhuma conta silenciada.")).toBeInTheDocument();
    });
  });

  it("2. Lista usuários silenciados com botão Reativar", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: {
        items: [
          { id: "1", username: "usuario_silenciado_1", avatar: null, muted_at: "2026-11-10T12:00:00Z" },
          { id: "2", username: "usuario_silenciado_2", avatar: "http://avatar.jpg", muted_at: "2026-11-09T10:00:00Z" },
        ],
      },
    });

    render(<SettingsMuted />);

    await waitFor(() => {
      expect(screen.getByText("@usuario_silenciado_1")).toBeInTheDocument();
      expect(screen.getByText("@usuario_silenciado_2")).toBeInTheDocument();
      expect(screen.getByTestId("unmute-btn-usuario_silenciado_1")).toBeInTheDocument();
      expect(screen.getByTestId("unmute-btn-usuario_silenciado_2")).toBeInTheDocument();
    });
  });

  it("3. Reativa usuário e permite Desfazer (Undo)", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: {
        items: [{ id: "1", username: "silenciado_teste", avatar: null }],
      },
    });
    vi.spyOn(api, "delete").mockResolvedValueOnce({});
    vi.spyOn(api, "post").mockResolvedValueOnce({});

    render(<SettingsMuted />);

    await waitFor(() => {
      expect(screen.getByText("@silenciado_teste")).toBeInTheDocument();
    });

    // Clica em Reativar
    const unmuteBtn = screen.getByTestId("unmute-btn-silenciado_teste");
    fireEvent.click(unmuteBtn);

    await waitFor(() => {
      expect(api.delete).toHaveBeenCalledWith("/api/social/mute/silenciado_teste/");
      expect(screen.getByText(/@silenciado_teste foi reativado/)).toBeInTheDocument();
      expect(screen.getByTestId("undo-unmute-btn")).toBeInTheDocument();
    });

    // Clica em Desfazer
    const undoBtn = screen.getByTestId("undo-unmute-btn");
    fireEvent.click(undoBtn);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/social/mute/silenciado_teste/");
      expect(screen.getByText("Ação desfeita.")).toBeInTheDocument();
      expect(screen.getByText("@silenciado_teste")).toBeInTheDocument();
    });
  });

  it("4. Trata erro ao carregar lista de silenciados", async () => {
    vi.spyOn(api, "get").mockRejectedValueOnce(new Error("Network Error"));

    render(<SettingsMuted />);

    await waitFor(() => {
      expect(screen.getByText("Algo deu errado. Tente novamente.")).toBeInTheDocument();
    });
  });
});
