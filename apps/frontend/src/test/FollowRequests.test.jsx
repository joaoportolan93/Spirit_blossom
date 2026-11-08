import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { FollowRequests } from "../pages/FollowRequests";
import { api } from "../services/api";
import "../i18n";

describe("FollowRequests Page Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. Renderiza estado vazio quando não há pedidos", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: { results: [], next_cursor: null },
    });

    render(
      <MemoryRouter>
        <FollowRequests />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId("requests-empty")).toBeInTheDocument();
      expect(screen.getByText("Nenhum pedido de seguir pendente.")).toBeInTheDocument();
    });
  });

  it("2. Lista pedidos de seguir com avatar e username", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: {
        results: [
          { id: 1, username: "alice", avatar: "http://example.com/alice.jpg", created_at: "2026-11-08T00:00:00Z" },
          { id: 2, username: "bob", avatar: null, created_at: "2026-11-08T00:01:00Z" },
        ],
        next_cursor: null,
      },
    });

    render(
      <MemoryRouter>
        <FollowRequests />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId("follow-request-alice")).toBeInTheDocument();
      expect(screen.getByTestId("follow-request-bob")).toBeInTheDocument();
      expect(screen.getByText("@alice")).toBeInTheDocument();
      expect(screen.getByText("@bob")).toBeInTheDocument();
    });
  });

  it("3. Aceita pedido com sucesso, remove item e exibe feedback", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: {
        results: [
          { id: 1, username: "alice", avatar: null, created_at: "2026-11-08T00:00:00Z" },
        ],
        next_cursor: null,
      },
    });
    vi.spyOn(api, "post").mockResolvedValueOnce({
      data: { detail: "Pedido aceito com sucesso.", status: "active" },
    });

    render(
      <MemoryRouter>
        <FollowRequests />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId("accept-btn-alice")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("accept-btn-alice"));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/social/follow-requests/alice/accept/");
      expect(screen.queryByTestId("follow-request-alice")).not.toBeInTheDocument();
      expect(screen.getByTestId("requests-feedback")).toHaveTextContent("Pedido aceito com sucesso.");
    });
  });

  it("4. Recusa pedido com sucesso, remove item e exibe feedback", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: {
        results: [
          { id: 2, username: "bob", avatar: null, created_at: "2026-11-08T00:00:00Z" },
        ],
        next_cursor: null,
      },
    });
    vi.spyOn(api, "post").mockResolvedValueOnce({
      data: { detail: "Pedido recusado com sucesso." },
    });

    render(
      <MemoryRouter>
        <FollowRequests />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId("reject-btn-bob")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("reject-btn-bob"));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/social/follow-requests/bob/reject/");
      expect(screen.queryByTestId("follow-request-bob")).not.toBeInTheDocument();
      expect(screen.getByTestId("requests-feedback")).toHaveTextContent("Pedido recusado.");
    });
  });

  it("5. Trata erro ao carregar pedidos", async () => {
    vi.spyOn(api, "get").mockRejectedValueOnce(new Error("Network Error"));

    render(
      <MemoryRouter>
        <FollowRequests />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId("requests-error")).toHaveTextContent("Erro ao carregar pedidos.");
    });
  });
});

