/**
 * Testes: usePushNotifications hook
 */

import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { usePushNotifications } from "../hooks/usePushNotifications";

// Mock do api
vi.mock("../services/api", () => ({
  api: {
    post: vi.fn().mockResolvedValue({ data: { id: "device-id", platform: "web" } }),
    delete: vi.fn().mockResolvedValue({ data: {} }),
  },
}));

// Mock do Firebase
vi.mock("../services/firebase", () => ({
  getFirebaseMessaging: vi.fn().mockResolvedValue({}),
  getVapidKey: vi.fn().mockReturnValue("test-vapid-key"),
}));

vi.mock("firebase/messaging", () => ({
  getToken: vi.fn().mockResolvedValue("mocked-fcm-token"),
  deleteToken: vi.fn().mockResolvedValue(true),
  onMessage: vi.fn((messaging, cb) => {
    cb({ notification: { title: "Hello", body: "World" } });
    return vi.fn();
  }),
}));

beforeEach(() => {
  vi.clearAllMocks();
  Object.defineProperty(global.navigator, "serviceWorker", {
    value: { register: vi.fn().mockResolvedValue({}) },
    configurable: true,
    writable: true,
  });
});

describe("usePushNotifications", () => {
  it("retorna isSupported=false quando Notification não definido", () => {
    const originalNotification = global.Notification;
    delete global.Notification;

    const { result } = renderHook(() => usePushNotifications({ enabled: true }));
    expect(result.current.isSupported).toBe(false);
    expect(result.current.permission).toBe("unsupported");

    global.Notification = originalNotification;
  });

  it("não registra token sem ação explícita do usuário", async () => {
    global.Notification = { permission: "default", requestPermission: vi.fn() };

    const { result } = renderHook(() => usePushNotifications({ enabled: true }));
    expect(result.current.isRegistered).toBe(false);
    expect(global.Notification.requestPermission).not.toHaveBeenCalled();
  });

  it("não dispara registro quando enabled=false", async () => {
    global.Notification = {
      permission: "granted",
      requestPermission: vi.fn().mockResolvedValue("granted"),
    };

    const { result } = renderHook(() => usePushNotifications({ enabled: false }));
    await act(async () => {
      await result.current.requestAndRegister();
    });

    expect(global.Notification.requestPermission).not.toHaveBeenCalled();
  });

  it("retorna permission=denied quando usuário nega", async () => {
    global.Notification = {
      permission: "default",
      requestPermission: vi.fn().mockResolvedValue("denied"),
    };

    const { result } = renderHook(() => usePushNotifications({ enabled: true }));

    await act(async () => {
      await result.current.requestAndRegister();
    });

    expect(result.current.permission).toBe("denied");
  });

  it("registra token com sucesso quando permissão é concedida", async () => {
    global.Notification = {
      permission: "default",
      requestPermission: vi.fn().mockResolvedValue("granted"),
    };

    const { result } = renderHook(() => usePushNotifications({ enabled: true }));

    await act(async () => {
      await result.current.requestAndRegister();
    });

    expect(result.current.isRegistered).toBe(true);
    const { api } = await import("../services/api");
    expect(api.post).toHaveBeenCalledWith(
      "/api/notifications/devices/",
      expect.objectContaining({ token: "mocked-fcm-token", platform: "web" })
    );
  });

  it("chama unregister e remove token", async () => {
    const { result } = renderHook(() => usePushNotifications({ enabled: true }));

    await act(async () => {
      await result.current.unregister();
    });

    expect(result.current.isRegistered).toBe(false);
    const { api } = await import("../services/api");
    expect(api.delete).toHaveBeenCalledWith(
      "/api/notifications/devices/",
      expect.objectContaining({ data: { token: "mocked-fcm-token" } })
    );
  });

  it("listenForeground escuta mensagens em foreground quando granted", async () => {
    global.Notification = {
      permission: "granted",
    };

    const { result } = renderHook(() => usePushNotifications({ enabled: true }));
    const received = [];

    await act(async () => {
      result.current.listenForeground((msg) => {
        received.push(msg);
      });
    });

    expect(typeof result.current.listenForeground).toBe("function");
  });
});
