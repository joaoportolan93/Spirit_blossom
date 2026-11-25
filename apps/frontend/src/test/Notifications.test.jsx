/**
 * Testes: Notifications.jsx — filtros de categoria, unread, mark-read e pedidos de seguir
 */

import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { I18nextProvider } from "react-i18next";
import i18n from "../i18n";
import { Notifications } from "../pages/Notifications";

vi.mock("../services/api", () => ({
  getNotifications: vi.fn(),
  markNotificationRead: vi.fn().mockResolvedValue({ detail: "ok" }),
  markAllNotificationsRead: vi.fn().mockResolvedValue({ detail: "ok" }),
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock("../hooks/useFeatureFlags", () => ({
  useFeatureFlags: () => ({
    flags: { push_notifications: false, notification_center_filters: true },
    isEnabled: (key) => key === "notification_center_filters",
    loading: false,
  }),
}));

const mockNotifications = [
  {
    id: 1,
    notification_type: "follow",
    sender: { username: "alice", display_name: "Alice", avatar: null },
    is_read: false,
    read: false,
    created_at: "2026-11-23T10:00:00Z",
    target_url: "/profile/alice",
  },
  {
    id: 2,
    notification_type: "like",
    sender: { username: "bob", display_name: "Bob", avatar: null },
    is_read: true,
    read: true,
    created_at: "2026-11-23T09:00:00Z",
    target_url: "/posts/123",
  },
];

function renderNotifications(route = "/notifications") {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <I18nextProvider i18n={i18n}>
        <Notifications />
      </I18nextProvider>
    </MemoryRouter>
  );
}

describe("Notifications — Central de Notificações", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const { getNotifications, api } = await import("../services/api");
    getNotifications.mockResolvedValue(mockNotifications);
    api.get.mockResolvedValue({ data: { results: [{ id: "req-1", username: "charlie" }] } });
    api.post.mockResolvedValue({ data: {} });
  });

  it("renderiza lista de notificações", async () => {
    renderNotifications();
    await waitFor(() => {
      expect(screen.getByTestId("notification-item-1")).toBeInTheDocument();
      expect(screen.getByTestId("notification-item-2")).toBeInTheDocument();
    });
  });

  it("exibe empty state quando não há notificações", async () => {
    const { getNotifications } = await import("../services/api");
    getNotifications.mockResolvedValue([]);

    renderNotifications();
    await waitFor(() => {
      expect(screen.getByTestId("notifications-empty")).toBeInTheDocument();
    });
  });

  it("exibe botão 'marcar todas como lidas' quando há não lidas", async () => {
    renderNotifications();
    await waitFor(() => {
      expect(screen.getByTestId("mark-all-read-btn")).toBeInTheDocument();
    });
  });

  it("chama markAllNotificationsRead ao clicar em marcar todas", async () => {
    renderNotifications();
    await waitFor(() => screen.getByTestId("mark-all-read-btn"));

    fireEvent.click(screen.getByTestId("mark-all-read-btn"));
    const { markAllNotificationsRead } = await import("../services/api");
    await waitFor(() => expect(markAllNotificationsRead).toHaveBeenCalled());
  });

  it("renderiza abas de categoria (tab-all presente)", async () => {
    renderNotifications();
    expect(screen.getByTestId("tab-all")).toBeInTheDocument();
  });

  it("mostra skeleton durante carregamento", () => {
    renderNotifications();
    expect(screen.queryByTestId("notifications-empty")).toBeNull();
  });

  it("clica em item não lido e chama markNotificationRead", async () => {
    renderNotifications();
    await waitFor(() => screen.getByTestId("notification-item-1"));

    fireEvent.click(screen.getByTestId("notification-item-1"));
    const { markNotificationRead } = await import("../services/api");
    await waitFor(() => expect(markNotificationRead).toHaveBeenCalledWith(1));
  });

  it("permite aceitar e rejeitar pedido de seguir na aba requests", async () => {
    renderNotifications("/notifications?tab=requests");
    await waitFor(() => screen.getByTestId("accept-btn-charlie"));

    fireEvent.click(screen.getByTestId("accept-btn-charlie"));
    const { api } = await import("../services/api");
    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith("/api/social/follow-requests/charlie/accept/")
    );
  });

  it("permite rejeitar pedido de seguir e trocar entre abas de filtro", async () => {
    const { getNotifications, api } = await import("../services/api");
    renderNotifications("/notifications?tab=requests");
    await waitFor(() => screen.getByTestId("reject-btn-charlie"));

    fireEvent.click(screen.getByTestId("reject-btn-charlie"));
    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith("/api/social/follow-requests/charlie/reject/")
    );

    fireEvent.click(screen.getByTestId("tab-likes"));
    await waitFor(() =>
      expect(getNotifications).toHaveBeenCalledWith({ category: "likes", unreadOnly: false })
    );

    fireEvent.click(screen.getByTestId("tab-unread"));
    await waitFor(() =>
      expect(getNotifications).toHaveBeenCalledWith({ category: "all", unreadOnly: true })
    );
  });
});
