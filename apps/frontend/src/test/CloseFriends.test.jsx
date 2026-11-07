import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CloseFriends } from "../pages/CloseFriends";
import { api } from "../services/api";
import "../i18n";

describe("CloseFriends Page Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. Carrega e exibe lista de amigos com e sem avatar", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: {
        results: [
          { username: "amigo1", avatar: null },
          { username: "amigo2", avatar: "http://example.com/avatar.png" },
        ],
      },
    });

    render(<CloseFriends />);

    expect(screen.getByText("Carregando...")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("@amigo1")).toBeInTheDocument();
      expect(screen.getByText("@amigo2")).toBeInTheDocument();
    });
  });

  it("2. Exibe estado vazio quando não há amigos no círculo", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: { results: [] },
    });

    render(<CloseFriends />);

    await waitFor(() => {
      expect(screen.getByTestId("empty-close-friends")).toBeInTheDocument();
    });
  });

  it("3. Permite adicionar amigo ao círculo com sucesso e ignora submit em branco", async () => {
    vi.spyOn(api, "get")
      .mockResolvedValueOnce({ data: { results: [] } })
      .mockResolvedValueOnce({ data: { results: [{ username: "novoamigo", avatar: null }] } });

    vi.spyOn(api, "post").mockResolvedValueOnce({
      data: { detail: "Adicionado ao círculo." },
    });

    render(<CloseFriends />);

    await waitFor(() => {
      expect(screen.getByTestId("add-close-friend-input")).toBeInTheDocument();
    });

    const input = screen.getByTestId("add-close-friend-input");
    const button = screen.getByTestId("add-close-friend-button");

    // Submit em branco não chama API
    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.click(button);
    expect(api.post).not.toHaveBeenCalled();

    // Submit com username válido
    fireEvent.change(input, { target: { value: "novoamigo" } });
    fireEvent.click(button);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/social/close-friends/novoamigo/");
      expect(screen.getByTestId("close-friends-action-message")).toHaveTextContent("Adicionado ao círculo.");
      expect(screen.getByText("@novoamigo")).toBeInTheDocument();
    });
  });

  it("4. Exibe mensagem de erro quando adicionar amigo falha", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({ data: { results: [] } });
    vi.spyOn(api, "post").mockRejectedValueOnce({
      response: { data: { detail: "Você precisa seguir este usuário" } },
    });

    render(<CloseFriends />);

    await waitFor(() => {
      expect(screen.getByTestId("add-close-friend-input")).toBeInTheDocument();
    });

    const input = screen.getByTestId("add-close-friend-input");
    const button = screen.getByTestId("add-close-friend-button");

    fireEvent.change(input, { target: { value: "desconhecido" } });
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByTestId("close-friends-error")).toHaveTextContent("Você precisa seguir este usuário");
    });
  });

  it("5. Permite remover amigo do círculo e lida com falha de remoção", async () => {
    vi.spyOn(api, "get")
      .mockResolvedValueOnce({
        data: { results: [{ username: "remover_amigo", avatar: null }] },
      })
      .mockResolvedValueOnce({ data: { results: [] } });

    vi.spyOn(api, "delete")
      .mockRejectedValueOnce({
        response: { data: { detail: "Erro ao remover" } },
      })
      .mockResolvedValueOnce({});

    render(<CloseFriends />);

    await waitFor(() => {
      expect(screen.getByText("@remover_amigo")).toBeInTheDocument();
    });

    const removeBtn = screen.getByTestId("remove-friend-remover_amigo");
    
    // 1ª tentativa falha
    fireEvent.click(removeBtn);
    await waitFor(() => {
      expect(screen.getByTestId("close-friends-error")).toHaveTextContent("Erro ao remover");
    });

    // 2ª tentativa tem sucesso
    fireEvent.click(removeBtn);
    await waitFor(() => {
      expect(screen.getByTestId("close-friends-action-message")).toHaveTextContent("Removido do círculo.");
    });
  });

  it("6. Trata erro na carga inicial de amigos", async () => {
    vi.spyOn(api, "get").mockRejectedValueOnce(new Error("Network Error"));

    render(<CloseFriends />);

    await waitFor(() => {
      expect(screen.getByTestId("close-friends-error")).toBeInTheDocument();
    });
  });
});
