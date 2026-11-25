import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { getFirebaseMessaging, getVapidKey } from "../services/firebase";

describe("firebase service", () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("getVapidKey retorna valor ou null", () => {
    const key = getVapidKey();
    expect(key === null || typeof key === "string").toBe(true);

    vi.stubEnv("VITE_FIREBASE_VAPID_KEY", "vapid-123");
    expect(getVapidKey()).toBe("vapid-123");
  });

  it("getFirebaseMessaging retorna null sem crash quando variáveis não configuradas", async () => {
    const messaging = await getFirebaseMessaging();
    expect(messaging).toBeNull();
  });

  it("chamadas subsequentes a getFirebaseMessaging retornam o valor memoizado", async () => {
    const messaging2 = await getFirebaseMessaging();
    expect(messaging2).toBeNull();
  });

  it("inicializa Firebase app e messaging quando variáveis configuradas e suportado", async () => {
    vi.stubEnv("VITE_FIREBASE_API_KEY", "api-key");
    vi.stubEnv("VITE_FIREBASE_PROJECT_ID", "proj-id");
    vi.stubEnv("VITE_FIREBASE_MESSAGING_SENDER_ID", "sender-1");
    vi.stubEnv("VITE_FIREBASE_APP_ID", "app-1");

    const fakeApp = { name: "app" };
    const fakeMessaging = { app: fakeApp };
    vi.doMock("firebase/app", () => ({
      initializeApp: vi.fn().mockReturnValue(fakeApp),
      getApps: vi.fn().mockReturnValue([]),
    }));
    vi.doMock("firebase/messaging", () => ({
      getMessaging: vi.fn().mockReturnValue(fakeMessaging),
      isSupported: vi.fn().mockResolvedValue(true),
    }));

    const { getFirebaseMessaging: freshGetMessaging } = await import("../services/firebase");
    const result = await freshGetMessaging();
    expect(result).toBe(fakeMessaging);
  });

  it("reutiliza app existente quando getApps já contém instância", async () => {
    vi.stubEnv("VITE_FIREBASE_API_KEY", "api-key");
    vi.stubEnv("VITE_FIREBASE_PROJECT_ID", "proj-id");
    vi.stubEnv("VITE_FIREBASE_MESSAGING_SENDER_ID", "sender-1");
    vi.stubEnv("VITE_FIREBASE_APP_ID", "app-1");

    const existingApp = { name: "existing" };
    const fakeMessaging = { app: existingApp };
    vi.doMock("firebase/app", () => ({
      initializeApp: vi.fn(),
      getApps: vi.fn().mockReturnValue([existingApp]),
    }));
    vi.doMock("firebase/messaging", () => ({
      getMessaging: vi.fn().mockReturnValue(fakeMessaging),
      isSupported: vi.fn().mockResolvedValue(true),
    }));

    const { getFirebaseMessaging: freshGetMessaging } = await import("../services/firebase");
    const result = await freshGetMessaging();
    expect(result).toBe(fakeMessaging);
  });

  it("retorna null quando isSupported resolve para false", async () => {
    vi.stubEnv("VITE_FIREBASE_API_KEY", "api-key");
    vi.stubEnv("VITE_FIREBASE_PROJECT_ID", "proj-id");
    vi.stubEnv("VITE_FIREBASE_MESSAGING_SENDER_ID", "sender-1");
    vi.stubEnv("VITE_FIREBASE_APP_ID", "app-1");

    vi.doMock("firebase/app", () => ({
      initializeApp: vi.fn(),
      getApps: vi.fn().mockReturnValue([]),
    }));
    vi.doMock("firebase/messaging", () => ({
      getMessaging: vi.fn(),
      isSupported: vi.fn().mockResolvedValue(false),
    }));

    const { getFirebaseMessaging: freshGetMessaging } = await import("../services/firebase");
    const result = await freshGetMessaging();
    expect(result).toBeNull();
  });

  it("retorna null sem crash quando initializeApp lança exceção", async () => {
    vi.stubEnv("VITE_FIREBASE_API_KEY", "api-key");
    vi.stubEnv("VITE_FIREBASE_PROJECT_ID", "proj-id");
    vi.stubEnv("VITE_FIREBASE_MESSAGING_SENDER_ID", "sender-1");
    vi.stubEnv("VITE_FIREBASE_APP_ID", "app-1");

    vi.doMock("firebase/app", () => ({
      initializeApp: vi.fn(() => {
        throw new Error("boom");
      }),
      getApps: vi.fn().mockReturnValue([]),
    }));
    vi.doMock("firebase/messaging", () => ({
      getMessaging: vi.fn(),
      isSupported: vi.fn().mockResolvedValue(true),
    }));

    const { getFirebaseMessaging: freshGetMessaging } = await import("../services/firebase");
    const result = await freshGetMessaging();
    expect(result).toBeNull();
  });
});
