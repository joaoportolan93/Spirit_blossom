import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { SettingsCircle } from "../pages/settings/SettingsCircle";
import { api } from "../services/api";
import "../i18n";

describe("SettingsCircle Component (Onda 3d)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. Renderiza estado vazio quando não há candidatos seguidores", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: { results: [], next_cursor: null },
    });

    render(<SettingsCircle />);

    expect(screen.getByText("Carregando...")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId("circle-empty")).toBeInTheDocument();
      expect(screen.getByText("Nenhum seguidor encontrado.")).toBeInTheDocument();
    });
  });

  it("2. Lista candidatos seguidores com status dentro ou fora do círculo", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: {
        results: [
          { username: "bob", avatar: null, is_close_friend: false },
          { username: "carol", avatar: null, is_close_friend: true },
        ],
        next_cursor: null,
      },
    });

    render(<SettingsCircle />);

    await waitFor(() => {
      expect(screen.getByText("@bob")).toBeInTheDocument();
      expect(screen.getByText("@carol")).toBeInTheDocument();
      expect(screen.getByTestId("toggle-circle-btn-bob")).toHaveTextContent("Adicionar");
      expect(screen.getByTestId("toggle-circle-btn-carol")).toHaveTextContent("Remover");
      expect(screen.getByText("No círculo")).toBeInTheDocument();
    });
  });

  it("3. Adiciona seguidor ao círculo com sucesso", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: {
        results: [{ username: "bob", avatar: null, is_close_friend: false }],
        next_cursor: null,
      },
    });
    vi.spyOn(api, "post").mockResolvedValueOnce({ data: { message: "ok" } });

    render(<SettingsCircle />);

    await waitFor(() => {
      expect(screen.getByTestId("toggle-circle-btn-bob")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("toggle-circle-btn-bob"));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/social/close-friends/bob/");
      expect(screen.getByTestId("circle-message")).toHaveTextContent("Adicionado ao círculo.");
      expect(screen.getByTestId("toggle-circle-btn-bob")).toHaveTextContent("Remover");
    });
  });

  it("4. Remove seguidor do círculo com sucesso", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: {
        results: [{ username: "carol", avatar: null, is_close_friend: true }],
        next_cursor: null,
      },
    });
    vi.spyOn(api, "delete").mockResolvedValueOnce({ data: { message: "ok" } });

    render(<SettingsCircle />);

    await waitFor(() => {
      expect(screen.getByTestId("toggle-circle-btn-carol")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("toggle-circle-btn-carol"));

    await waitFor(() => {
      expect(api.delete).toHaveBeenCalledWith("/api/social/close-friends/carol/");
      expect(screen.getByTestId("circle-message")).toHaveTextContent("Removido do círculo.");
      expect(screen.getByTestId("toggle-circle-btn-carol")).toHaveTextContent("Adicionar");
    });
  });

  it("5. Busca seguidores pelo campo de texto", async () => {
    vi.spyOn(api, "get").mockImplementation((url, config) => {
      if (config?.params?.q === "dan") {
        return Promise.resolve({
          data: {
            results: [{ username: "daniel", avatar: null, is_close_friend: false }],
            next_cursor: null,
          },
        });
      }
      return Promise.resolve({ data: { results: [], next_cursor: null } });
    });

    render(<SettingsCircle />);

    const searchInput = screen.getByTestId("circle-search-input");
    fireEvent.change(searchInput, { target: { value: "dan" } });

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("/api/social/close-friends/candidates/", {
        params: { q: "dan" },
      });
      expect(screen.getByText("@daniel")).toBeInTheDocument();
    });
  });
});

