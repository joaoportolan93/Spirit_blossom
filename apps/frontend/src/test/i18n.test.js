import { describe, it, expect } from "vitest";
import ptBR from "../locales/pt-BR.json";
import en from "../locales/en.json";
import i18n from "../i18n";
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
});

