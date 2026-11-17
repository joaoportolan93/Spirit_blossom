import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { Settings } from "../pages/Settings";
import { SettingsPrivacy } from "../pages/settings/SettingsPrivacy";
import { SettingsCircle } from "../pages/settings/SettingsCircle";
import { SettingsAccount } from "../pages/settings/SettingsAccount";
import { SettingsNotifications } from "../pages/settings/SettingsNotifications";
import { AuthContext } from "../hooks/useAuth";
import "../i18n";

// Mock api module
vi.mock("../services/api", () => ({
  api: {
    get: vi.fn().mockResolvedValue({ data: { is_private: false, show_likes_tab: true, notify_likes: true, notify_comments: true, notify_follows: true, notify_mentions: true, bio: "", username: "alice" } }),
    patch: vi.fn().mockResolvedValue({ data: { is_private: false } }),
    post: vi.fn().mockResolvedValue({ data: {} }),
  },
  updateUserSettings: vi.fn().mockResolvedValue({ data: {} }),
  changePassword: vi.fn().mockResolvedValue({ data: {} }),
  getUserSettings: vi.fn().mockResolvedValue({ data: {} }),
}));

function renderSettings(initialRoute = "/settings/account") {
  const authValue = {
    user: { username: "alice", theme: "dark", language: "pt-BR" },
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
  };

  return render(
    <AuthContext.Provider value={authValue}>
      <MemoryRouter initialEntries={[initialRoute]}>
        <Routes>
          <Route path="/settings" element={<Settings />}>
            <Route path="account" element={<SettingsAccount />} />
            <Route path="notifications" element={<SettingsNotifications />} />
            <Route path="privacy" element={<SettingsPrivacy />} />
            <Route path="circle" element={<SettingsCircle />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>
  );
}

describe("Settings Page Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. Renderiza título e 4 abas de navegação de configurações", () => {
    renderSettings("/settings/account");

    expect(screen.getByRole("heading", { name: "Configurações" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Conta" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Notificações" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Visibilidade" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Aparência e Idioma" })).toBeInTheDocument();
  });

  it("2. Aba Conta está ativa na rota /settings/account", () => {
    renderSettings("/settings/account");
    expect(screen.getByRole("link", { name: "Conta" })).toHaveClass("text-white");
  });

  it("3. Aba Visibilidade está ativa na rota /settings/privacy", () => {
    renderSettings("/settings/privacy");
    expect(screen.getByRole("link", { name: "Visibilidade" })).toHaveClass("text-white");
  });

  it("4. Aba Notificações está ativa na rota /settings/notifications", () => {
    renderSettings("/settings/notifications");
    expect(screen.getByRole("link", { name: "Notificações" })).toHaveClass("text-white");
  });
});
