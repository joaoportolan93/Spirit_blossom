import "@testing-library/jest-dom";
import i18n from "../i18n";

if (typeof window !== "undefined") {
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
}

beforeEach(() => {
  i18n.changeLanguage("pt-BR");
});
