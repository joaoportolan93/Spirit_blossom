import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Notifications } from "../pages/Notifications";
import { api } from "../services/api";
import "../i18n";

function renderNotifications(initialRoute = "/notifications") {
  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <Notifications />
    </MemoryRouter>
  );
}

describe("Notifications Page Component (Onda 3d)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. Renderiza aba 'Todas' por padrão e lista notificações", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/notifications/")) {
        return Promise.resolve({
          data: [
            {
              id: 1,
              actor: { username: "bob" },
              verb: "like",
              is_read: false,
              created_at: "2026-11-08T12:00:00Z",
            },
          ],
        });
      }
      if (url.includes("/api/social/follow-requests/")) {
        return Promise.resolve({ data: { results: [] } });
      }
      return Promise.resolve({ data: [] });
    });

    renderNotifications("/notifications");

    await waitFor(() => {
      expect(screen.getByText("Notificações")).toBeInTheDocument();
      expect(screen.getByText("bob")).toBeInTheDocument();
      expect(screen.getByTestId("mark-all-read-btn")).toBeInTheDocument();
    });
  });

  it("2. Alterna para aba 'Pedidos de seguir' e lista pedidos pendentes", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/social/follow-requests/")) {
        return Promise.resolve({
          data: {
            results: [{ username: "charlie", avatar: null, created_at: "2026-11-08" }],
          },
        });
      }
      return Promise.resolve({ data: [] });
    });

    renderNotifications("/notifications?tab=requests");

    await waitFor(() => {
      expect(screen.getByText("@charlie")).toBeInTheDocument();
      expect(screen.getByTestId("accept-btn-charlie")).toBeInTheDocument();
      expect(screen.getByTestId("reject-btn-charlie")).toBeInTheDocument();
    });
  });

  it("3. Aceita pedido de seguir com sucesso", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/social/follow-requests/")) {
        return Promise.resolve({
          data: {
            results: [{ username: "charlie", avatar: null }],
          },
        });
      }
      return Promise.resolve({ data: [] });
    });
    vi.spyOn(api, "post").mockResolvedValueOnce({ data: { message: "accepted" } });

    renderNotifications("/notifications?tab=requests");

    await waitFor(() => {
      expect(screen.getByTestId("accept-btn-charlie")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("accept-btn-charlie"));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/social/follow-requests/charlie/accept/");
      expect(screen.getByTestId("requests-feedback")).toHaveTextContent(
        "Pedido aceito com sucesso."
      );
    });
  });

  it("4. Recusa pedido de seguir com sucesso", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/social/follow-requests/")) {
        return Promise.resolve({
          data: {
            results: [{ username: "dave", avatar: null }],
          },
        });
      }
      return Promise.resolve({ data: [] });
    });
    vi.spyOn(api, "post").mockResolvedValueOnce({ data: { message: "rejected" } });

    renderNotifications("/notifications?tab=requests");

    await waitFor(() => {
      expect(screen.getByTestId("reject-btn-dave")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("reject-btn-dave"));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/social/follow-requests/dave/reject/");
      expect(screen.getByTestId("requests-feedback")).toHaveTextContent("Pedido recusado.");
    });
  });
});
