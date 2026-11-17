import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import ptBR from "./locales/pt-BR.json";
import en from "./locales/en.json";

export const BRAZIL_TIMEZONES = [
  "America/Sao_Paulo",
  "America/Fortaleza",
  "America/Recife",
  "America/Belem",
  "America/Manaus",
  "America/Cuiaba",
  "America/Porto_Velho",
  "America/Boa_Vista",
  "America/Rio_Branco",
  "America/Maceio",
  "America/Bahia",
  "America/Araguaina",
  "America/Campo_Grande",
  "America/Noronha",
  "America/Santarem",
  "America/Eirunepe",
];

export function detectBrowserLanguage() {
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (tz && BRAZIL_TIMEZONES.includes(tz)) {
      return "pt-BR";
    }
  } catch {
    // Falha silenciosa em ambientes sem suporte a Intl timezone
  }

  try {
    if (navigator?.language?.toLowerCase().startsWith("pt")) {
      return "pt-BR";
    }
  } catch {
    // Falha silenciosa
  }

  return "en";
}

export function resolveInitialLanguage(userLanguage = null) {
  if (userLanguage && (userLanguage === "pt-BR" || userLanguage === "en")) {
    return userLanguage;
  }
  try {
    const saved = localStorage.getItem("lumem_language");
    if (saved && (saved === "pt-BR" || saved === "en")) {
      return saved;
    }
  } catch {
    // localStorage indisponível
  }
  return detectBrowserLanguage();
}

i18n.use(initReactI18next).init({
  resources: {
    "pt-BR": { translation: ptBR },
    en: { translation: en },
  },
  lng: resolveInitialLanguage(),
  fallbackLng: "en",
  interpolation: {
    escapeValue: false, // React já protege contra XSS
  },
});

export default i18n;
