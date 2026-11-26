import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { FollowSuggestions } from "../components/FollowSuggestions";
import { Feed } from "../pages/Feed";
import { AuthContext } from "../hooks/useAuth";
import { api } from "../services/api";
import "../i18n";

describe("FollowSuggestions Component (Onda 7b)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. Não renderiza nada quando não há sugestões (zero widget vazio)", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({ data: { results: [] } });

    const { container } = render(
      <MemoryRouter>
        <FollowSuggestions />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("/api/social/suggestions/?limit=5");
    });
    expect(container.querySelector("[data-testid='follow-suggestions']")).toBeNull();
  });

  it("2. Exibe sugestões mútuas e da comunidade com botão seguir e estado pendente", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: {
        results: [
          {
            id: "u1",
            username: "alice",
            display_name: "Alice Silva",
            avatar: null,
            is_private: true,
            mutual_count: 3,
            mutual_sample_username: "bob",
            reason: "mutual",
          },
          {
            id: "u2",
            username: "carol",
            display_name: "",
            avatar: null,
            is_private: false,
            mutual_count: 0,
            mutual_sample_username: null,
            reason: "active_community",
          },
        ],
      },
    });
    vi.spyOn(api, "post").mockResolvedValueOnce({
      data: { detail: "Pedido de seguir enviado.", status: "pending" },
    });

    render(
      <MemoryRouter>
        <FollowSuggestions />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId("follow-suggestions")).toBeInTheDocument();
    });

    expect(screen.getByText("Alice Silva")).toBeInTheDocument();
    expect(screen.getByText("@alice")).toBeInTheDocument();
    expect(screen.getByText("Seguido por @bob e +2")).toBeInTheDocument();
    expect(screen.getByText("@carol")).toBeInTheDocument();
    expect(screen.getByText("Ativo na comunidade")).toBeInTheDocument();

    const followButtons = screen.getAllByTestId("follow-button");
    fireEvent.click(followButtons[0]);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/social/follow/alice/");
      expect(followButtons[0]).toHaveTextContent("Solicitado");
    });
  });

  it("3. Integra FollowSuggestions e links legais na sidebar do Feed autenticado", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.startsWith("/api/social/suggestions/")) {
        return Promise.resolve({
          data: {
            results: [
              {
                id: "u9",
                username: "diana",
                display_name: "Diana",
                avatar: null,
                is_private: false,
                mutual_count: 1,
                mutual_sample_username: "carlos",
                reason: "mutual",
              },
            ],
          },
        });
      }
      return Promise.resolve({ data: [] });
    });

    render(
      <AuthContext.Provider value={{ user: { username: "me" }, loading: false }}>
        <MemoryRouter>
          <Feed />
        </MemoryRouter>
      </AuthContext.Provider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("follow-suggestions")).toBeInTheDocument();
      expect(screen.getByText("Seguido por @carlos")).toBeInTheDocument();
    });

    expect(screen.getByRole("link", { name: "Política de Privacidade" })).toHaveAttribute(
      "href",
      "/privacy"
    );
    expect(screen.getByRole("link", { name: "Termos de Uso" })).toHaveAttribute(
      "href",
      "/terms"
    );
  });
});
