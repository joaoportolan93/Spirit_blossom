import { describe, it, expect } from "vitest";
import { formatDistanceToNow } from "../utils/date";

describe("Date utils - formatDistanceToNow", () => {
  it("retorna 'agora' para menos de 60 segundos", () => {
    const now = new Date().toISOString();
    expect(formatDistanceToNow(now)).toBe("agora");
  });

  it("retorna minutos para menos de 60 minutos", () => {
    const tenMinutesAgo = new Date(Date.now() - 10 * 60 * 1000).toISOString();
    expect(formatDistanceToNow(tenMinutesAgo)).toBe("10m");
  });

  it("retorna horas para menos de 24 horas", () => {
    const threeHoursAgo = new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString();
    expect(formatDistanceToNow(threeHoursAgo)).toBe("3h");
  });

  it("retorna dias para mais de 24 horas", () => {
    const twoDaysAgo = new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString();
    expect(formatDistanceToNow(twoDaysAgo)).toBe("2d");
  });

  it("retorna string vazia para entrada inválida", () => {
    expect(formatDistanceToNow("invalid-date-string-that-causes-nan")).toBe("");
  });
});
