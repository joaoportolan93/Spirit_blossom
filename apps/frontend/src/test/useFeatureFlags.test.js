/**
 * Testes: useFeatureFlags hook (Onda 7a)
 */

import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useFeatureFlags } from "../hooks/useFeatureFlags";

// Mock do módulo api
vi.mock("../services/api", () => ({
  api: {
    get: vi.fn(),
  },
}));

beforeEach(() => {
  sessionStorage.clear();
  vi.clearAllMocks();
});

describe("useFeatureFlags", () => {
  it("retorna flags do servidor", async () => {
    const { api } = await import("../services/api");
    api.get.mockResolvedValue({
      data: { flags: { push_notifications: true, notification_center_filters: false } },
    });

    const { result } = renderHook(() => useFeatureFlags());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.isEnabled("push_notifications")).toBe(true);
    expect(result.current.isEnabled("notification_center_filters")).toBe(false);
  });

  it("retorna false para flag inexistente (default seguro)", async () => {
    const { api } = await import("../services/api");
    api.get.mockResolvedValue({ data: { flags: {} } });

    const { result } = renderHook(() => useFeatureFlags());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.isEnabled("flag_inexistente")).toBe(false);
  });

  it("degradação graciosa em caso de erro de rede", async () => {
    const { api } = await import("../services/api");
    api.get.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useFeatureFlags());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.isEnabled("push_notifications")).toBe(false);
    expect(result.current.flags).toEqual({});
  });

  it("lê cache do sessionStorage sem nova requisição", async () => {
    const { api } = await import("../services/api");
    const cached = { push_notifications: true };
    sessionStorage.setItem(
      "feature_flags_cache",
      JSON.stringify({ flags: cached, ts: Date.now() })
    );

    const { result } = renderHook(() => useFeatureFlags());
    // Loading não é true porque cache existe
    expect(result.current.isEnabled("push_notifications")).toBe(true);
    expect(api.get).not.toHaveBeenCalled();
  });
});
