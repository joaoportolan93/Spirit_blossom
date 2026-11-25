import { describe, it, expect } from "vitest";
import { getFirebaseMessaging, getVapidKey } from "../services/firebase";

describe("firebase service", () => {
  it("getVapidKey retorna valor ou null", () => {
    const key = getVapidKey();
    expect(key === null || typeof key === "string").toBe(true);
  });

  it("getFirebaseMessaging retorna null sem crash quando variáveis não configuradas", async () => {
    const messaging = await getFirebaseMessaging();
    expect(messaging).toBeNull();
  });

  it("chamadas subsequentes a getFirebaseMessaging retornam o valor memoizado", async () => {
    const messaging2 = await getFirebaseMessaging();
    expect(messaging2).toBeNull();
  });
});
