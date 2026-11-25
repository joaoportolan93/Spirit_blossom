/**
 * Testes: NotificationBell (Onda 7a — unread count via /api/notifications/unread-count/)
 */

import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { I18nextProvider } from "react-i18next";
import i18n from "../i18n";
import { NotificationBell } from "../components/NotificationBell";

vi.mock("../services/api", () => ({
  getUnreadCount: vi.fn(),
}));

function renderBell() {
  return render(
    <MemoryRouter>
      <I18nextProvider i18n={i18n}>
        <NotificationBell />
      </I18nextProvider>
    </MemoryRouter>
  );
}

describe("NotificationBell — Badge e polling", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renderiza botão sem badge quando unread=0", async () => {
    const { getUnreadCount } = await import("../services/api");
    getUnreadCount.mockResolvedValue(0);

    renderBell();
    expect(screen.getByTestId("notification-bell-btn")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByTestId("unread-badge")).toBeNull());
  });

  it("exibe badge com contagem quando há não lidas", async () => {
    const { getUnreadCount } = await import("../services/api");
    getUnreadCount.mockResolvedValue(5);

    renderBell();
    await waitFor(() => {
      const badge = screen.getByTestId("unread-badge");
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveTextContent("5");
    });
  });

  it("exibe 99+ quando contagem > 99", async () => {
    const { getUnreadCount } = await import("../services/api");
    getUnreadCount.mockResolvedValue(150);

    renderBell();
    await waitFor(() => {
      expect(screen.getByTestId("unread-badge")).toHaveTextContent("99+");
    });
  });

  it("não crasha quando API retorna erro", async () => {
    const { getUnreadCount } = await import("../services/api");
    getUnreadCount.mockRejectedValue(new Error("Network error"));

    renderBell();
    // Sem badge, sem crash
    await waitFor(() => expect(screen.queryByTestId("unread-badge")).toBeNull());
  });
});
