/**
 * Gerenciamento centralizado de temas da aplicação.
 * Suporta 3 opções: light (Branco), dark (Preto) e oled (Preto OLED #000000).
 */

export const VALID_THEMES = ["light", "dark", "oled"];

export function applyTheme(theme) {
  const chosen = VALID_THEMES.includes(theme) ? theme : "light";
  if (typeof document !== "undefined" && document.documentElement) {
    document.documentElement.setAttribute("data-theme", chosen);
  }
  try {
    localStorage.setItem("spirit_theme", chosen);
  } catch {
    // LocalStorage indisponível
  }
  return chosen;
}

export function getInitialTheme(userTheme = null) {
  if (userTheme && VALID_THEMES.includes(userTheme)) {
    return userTheme;
  }
  try {
    const saved = localStorage.getItem("spirit_theme");
    if (saved && VALID_THEMES.includes(saved)) {
      return saved;
    }
  } catch {
    // LocalStorage indisponível
  }
  return "light";
}
