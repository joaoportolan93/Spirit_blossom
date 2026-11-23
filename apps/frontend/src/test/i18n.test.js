import { describe, it, expect, vi, beforeEach } from "vitest";
import ptBR from "../locales/pt-BR.json";
import en from "../locales/en.json";
import i18n, { detectBrowserLanguage, resolveInitialLanguage } from "../i18n";
import { api } from "../services/api";

function getLeafKeys(obj, prefix = "") {
  let keys = [];
  for (const [key, value] of Object.entries(obj)) {
    const currentKey = prefix ? `${prefix}.${key}` : key;
    if (value !== null && typeof value === "object" && !Array.isArray(value)) {
      keys = keys.concat(getLeafKeys(value, currentKey));
    } else {
      keys.push(currentKey);
    }
  }
  return keys.sort();
}

describe("i18n Localization & Accept-Language (ADR-N23)", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("1. Garante paridade total de chaves entre pt-BR.json e en.json", () => {
    const ptKeys = getLeafKeys(ptBR);
    const enKeys = getLeafKeys(en);

    const missingInEn = ptKeys.filter((k) => !enKeys.includes(k));
    const missingInPt = enKeys.filter((k) => !ptKeys.includes(k));

    expect(missingInEn).toEqual([]);
    expect(missingInPt).toEqual([]);
  });

  it("2. O interceptor do Axios anexa o cabeçalho Accept-Language conforme idioma ativo", async () => {
    i18n.changeLanguage("pt-BR");
    const configPt = await api.interceptors.request.handlers[0].fulfilled({
      headers: {},
    });
    expect(configPt.headers["Accept-Language"]).toBe("pt-BR");

    i18n.changeLanguage("en");
    const configEn = await api.interceptors.request.handlers[0].fulfilled({
      headers: {},
    });
    expect(configEn.headers["Accept-Language"]).toBe("en");

    // Restaura idioma padrão
    i18n.changeLanguage("pt-BR");
  });

  it("3. detectBrowserLanguage retorna pt-BR quando fuso horário for brasileiro", () => {
    vi.spyOn(Intl, "DateTimeFormat").mockImplementation(() => ({
      resolvedOptions: () => ({ timeZone: "America/Sao_Paulo" }),
    }));
    expect(detectBrowserLanguage()).toBe("pt-BR");
  });

  it("4. detectBrowserLanguage retorna pt-BR quando navigator.language inicia com pt", () => {
    vi.spyOn(Intl, "DateTimeFormat").mockImplementation(() => ({
      resolvedOptions: () => ({ timeZone: "Europe/London" }),
    }));
    Object.defineProperty(window.navigator, "language", {
      value: "pt-PT",
      configurable: true,
    });
    expect(detectBrowserLanguage()).toBe("pt-BR");
  });

  it("5. detectBrowserLanguage retorna en para outros fusos e idiomas", () => {
    vi.spyOn(Intl, "DateTimeFormat").mockImplementation(() => ({
      resolvedOptions: () => ({ timeZone: "Europe/London" }),
    }));
    Object.defineProperty(window.navigator, "language", {
      value: "en-US",
      configurable: true,
    });
    expect(detectBrowserLanguage()).toBe("en");
  });

  it("6. resolveInitialLanguage respeita ordem de prioridade (user > localStorage > auto)", () => {
    localStorage.setItem("spirit_language", "en");
    expect(resolveInitialLanguage("pt-BR")).toBe("pt-BR");
    expect(resolveInitialLanguage(null)).toBe("en");
  });
});
