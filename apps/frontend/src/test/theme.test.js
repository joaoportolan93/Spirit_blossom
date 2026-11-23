import { describe, it, expect, beforeEach } from "vitest";
import { applyTheme, getInitialTheme, VALID_THEMES } from "../utils/theme";

describe("Theme Utils (Onda 5)", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  it("1. Possui exatamente 3 temas válidos (light, dark, oled)", () => {
    expect(VALID_THEMES).toEqual(["light", "dark", "oled"]);
  });

  it("2. applyTheme define data-theme no documentElement e persiste no localStorage", () => {
    expect(applyTheme("oled")).toBe("oled");
    expect(document.documentElement.getAttribute("data-theme")).toBe("oled");
    expect(localStorage.getItem("spirit_theme")).toBe("oled");

    expect(applyTheme("dark")).toBe("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");

    // Tema inválido recorre a light
    expect(applyTheme("invalid")).toBe("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("3. getInitialTheme prioriza preferência do usuário, depois localStorage, depois default light", () => {
    expect(getInitialTheme("dark")).toBe("dark");

    localStorage.setItem("spirit_theme", "oled");
    expect(getInitialTheme(null)).toBe("oled");

    localStorage.clear();
    expect(getInitialTheme(null)).toBe("light");
  });
});
