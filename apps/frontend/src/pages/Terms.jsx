import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { APP_NAME } from "../config/brand";

export function Terms() {
  const { t } = useTranslation();

  const sections = [
    {
      title: t("legal.terms_age_title"),
      body: t("legal.terms_age_body", { appName: APP_NAME }),
    },
    {
      title: t("legal.terms_feed_title"),
      body: t("legal.terms_feed_body"),
    },
    {
      title: t("legal.terms_conduct_title"),
      body: t("legal.terms_conduct_body"),
    },
    {
      title: t("legal.terms_ip_title"),
      body: t("legal.terms_ip_body"),
    },
    {
      title: t("legal.terms_termination_title"),
      body: t("legal.terms_termination_body"),
    },
  ];

  return (
    <article
      data-testid="terms-page"
      className="max-w-[65ch] mx-auto px-4 py-10 space-y-6"
    >
      <header className="space-y-2 border-b border-zinc-800 pb-6">
        <p className="text-xs font-medium text-pink-400 uppercase tracking-wider">
          {APP_NAME}
        </p>
        <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
          {t("legal.terms_title")}
        </h1>
        <p className="text-sm text-zinc-300 leading-relaxed">
          {t("legal.terms_subtitle", { appName: APP_NAME })}
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
        <Link to="/privacy" className="text-pink-400 hover:underline">
          {t("legal.privacy_link")}
        </Link>
        <Link to="/" className="hover:text-zinc-200 transition">
          {t("common.back")}
        </Link>
      </footer>
    </article>
  );
}

export default Terms;
