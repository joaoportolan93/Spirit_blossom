import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { APP_NAME } from "../config/brand";

export function Privacy() {
  const { t } = useTranslation();

  const sections = [
    {
      title: t("legal.privacy_data_title"),
      body: t("legal.privacy_data_body"),
    },
    {
      title: t("legal.privacy_controls_title"),
      body: t("legal.privacy_controls_body"),
    },
    {
      title: t("legal.privacy_retention_title"),
      body: t("legal.privacy_retention_body"),
    },
    {
      title: t("legal.privacy_lgpd_title"),
      body: t("legal.privacy_lgpd_body"),
    },
  ];

  return (
    <article
      data-testid="privacy-page"
      className="max-w-[65ch] mx-auto px-4 py-10 space-y-6"
    >
      <header className="space-y-2 border-b border-zinc-800 pb-6">
        <p className="text-xs font-medium text-pink-400 uppercase tracking-wider">
          {APP_NAME}
        </p>
        <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
          {t("legal.privacy_title")}
        </h1>
        <p className="text-sm text-zinc-300 leading-relaxed">
          {t("legal.privacy_subtitle")}
        </p>
        <p className="text-xs text-zinc-500">{t("legal.last_updated")}</p>
      </header>

      <div className="space-y-6">
        {sections.map((section) => (
          <section key={section.title} className="space-y-2">
            <h2 className="text-base font-semibold text-white">
              {section.title}
            </h2>
            <p className="text-sm text-zinc-300 leading-relaxed">
              {section.body}
            </p>
          </section>
        ))}
      </div>

      <footer className="pt-6 border-t border-zinc-800 flex items-center justify-between text-xs text-zinc-400">
        <Link to="/terms" className="text-pink-400 hover:underline">
          {t("legal.terms_link")}
        </Link>
        <Link to="/" className="hover:text-zinc-200 transition">
          {t("common.back")}
        </Link>
      </footer>
    </article>
  );
}

export default Privacy;
