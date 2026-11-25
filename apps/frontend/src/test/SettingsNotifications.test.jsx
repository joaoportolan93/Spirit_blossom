/**
 * Testes: SettingsNotifications (Onda 7a — controle de push + toggles)
 */

import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { I18nextProvider } from "react-i18next";
import i18n from "../i18n";
import { SettingsNotifications } from "../pages/settings/SettingsNotifications";

vi.mock("../services/api", () => ({
  getUserSettings: vi.fn().mockResolvedValue({
    notify_likes: true,
    notify_comments: true,
    notify_follows: true,
    notify_mentions: true,
  }),
  updateUserSettings: vi.fn().mockResolvedValue({}),
}));

vi.mock("../hooks/useFeatureFlags", () => ({
  useFeatureFlags: vi.fn(() => ({
    flags: { push_notifications: false },
    isEnabled: () => false,
    loading: false,
  })),
}));

vi.mock("../hooks/usePushNotifications", () => ({
  usePushNotifications: vi.fn(() => ({
    permission: "default",
    isSupported: false,
    isRegistered: false,
    loading: false,
    error: null,
    requestAndRegister: vi.fn(),
    unregister: vi.fn(),
  })),
}));

function renderSettings() {
  return render(
    <MemoryRouter>
      <I18nextProvider i18n={i18n}>
        <SettingsNotifications />
      </I18nextProvider>
    </MemoryRouter>
  );
}

describe("SettingsNotifications — Preferências e Push", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renderiza todos os 4 toggles de notificação", async () => {
    renderSettings();
    await waitFor(() => {
      expect(screen.getByTestId("notify-likes-toggle")).toBeInTheDocument();
      expect(screen.getByTestId("notify-comments-toggle")).toBeInTheDocument();
      expect(screen.getByTestId("notify-follows-toggle")).toBeInTheDocument();
      expect(screen.getByTestId("notify-mentions-toggle")).toBeInTheDocument();
    });
  });

  it("chama updateUserSettings ao toglar preferência", async () => {
    renderSettings();
    await waitFor(() => screen.getByTestId("notify-likes-toggle"));

    fireEvent.click(screen.getByTestId("notify-likes-toggle"));

    const { updateUserSettings } = await import("../services/api");
    await waitFor(() => expect(updateUserSettings).toHaveBeenCalledWith({ notify_likes: false }));
  });

  it("exibe mensagem de sucesso após salvar", async () => {
    renderSettings();
    await waitFor(() => screen.getByTestId("notify-likes-toggle"));

    fireEvent.click(screen.getByTestId("notify-likes-toggle"));
    await waitFor(() => {
      expect(screen.getByTestId("notifications-success")).toBeInTheDocument();
    });
  });

  it("não exibe botão push quando feature flag desabilitada", async () => {
    renderSettings();
    await waitFor(() => screen.getByTestId("notify-likes-toggle"));
    // push_notifications=false → botão enable-push não renderizado
    expect(screen.queryByTestId("enable-push-btn")).toBeNull();
  });

  it("exibe botão de ativar push e chama requestAndRegister quando flag ativa", async () => {
    const { useFeatureFlags } = await import("../hooks/useFeatureFlags");
    const { usePushNotifications } = await import("../hooks/usePushNotifications");
    const mockRequest = vi.fn();

    useFeatureFlags.mockReturnValue({
      flags: { push_notifications: true },
      isEnabled: (k) => k === "push_notifications",
      loading: false,
    });
    usePushNotifications.mockReturnValue({
      permission: "default",
      isSupported: true,
      isRegistered: false,
      loading: false,
      error: null,
      requestAndRegister: mockRequest,
      unregister: vi.fn(),
    });

    renderSettings();
    await waitFor(() => screen.getByTestId("enable-push-btn"));
    fireEvent.click(screen.getByTestId("enable-push-btn"));
    expect(mockRequest).toHaveBeenCalled();
  });

  it("exibe botão de desativar push e chama unregister quando já registrado", async () => {
    const { useFeatureFlags } = await import("../hooks/useFeatureFlags");
    const { usePushNotifications } = await import("../hooks/usePushNotifications");
    const mockUnregister = vi.fn();

    useFeatureFlags.mockReturnValue({
      flags: { push_notifications: true },
      isEnabled: (k) => k === "push_notifications",
      loading: false,
    });
    usePushNotifications.mockReturnValue({
      permission: "granted",
      isSupported: true,
      isRegistered: true,
      loading: false,
      error: null,
      requestAndRegister: vi.fn(),
      unregister: mockUnregister,
    });

    renderSettings();
    await waitFor(() => screen.getByTestId("disable-push-btn"));
    fireEvent.click(screen.getByTestId("disable-push-btn"));
    expect(mockUnregister).toHaveBeenCalled();
  });

  it("exibe aviso de bloqueio quando permission é denied", async () => {
    const { useFeatureFlags } = await import("../hooks/useFeatureFlags");
    const { usePushNotifications } = await import("../hooks/usePushNotifications");

    useFeatureFlags.mockReturnValue({
      flags: { push_notifications: true },
      isEnabled: (k) => k === "push_notifications",
      loading: false,
    });
    usePushNotifications.mockReturnValue({
      permission: "denied",
      isSupported: true,
      isRegistered: false,
      loading: false,
      error: null,
      requestAndRegister: vi.fn(),
      unregister: vi.fn(),
    });

    renderSettings();
    await waitFor(() => {
      expect(screen.getByText(/Bloqueado/i)).toBeInTheDocument();
    });
  });

  it("exibe erro ao falhar carregamento ou salvamento de preferências", async () => {
    const { updateUserSettings } = await import("../services/api");
    updateUserSettings.mockRejectedValueOnce(new Error("fail"));

    renderSettings();
    await waitFor(() => screen.getByTestId("notify-likes-toggle"));
    fireEvent.click(screen.getByTestId("notify-likes-toggle"));

    await waitFor(() => {
      expect(screen.getByTestId("notifications-error")).toBeInTheDocument();
    });
  });
});
