import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { Settings } from "../pages/Settings";
import { SettingsPrivacy } from "../pages/settings/SettingsPrivacy";
import { SettingsCircle } from "../pages/settings/SettingsCircle";
import { AuthContext } from "../hooks/useAuth";
import "../i18n";

function renderSettings(initialRoute = "/settings/privacy") {
  const authValue = {
    user: { username: "alice" },
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
  };

  return render(
    <AuthContext.Provider value={authValue}>
      <MemoryRouter initialEntries={[initialRoute]}>
        <Routes>
          <Route path="/settings" element={<Settings />}>
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

  it("1. Renderiza título e abas de navegação de configurações", () => {
    renderSettings("/settings/privacy");

    expect(screen.getByRole("heading", { name: "Configurações" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Privacidade" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Círculo de amigos" })).toBeInTheDocument();
  });

  it("2. Renderiza aba de Privacidade na rota /settings/privacy", () => {
    renderSettings("/settings/privacy");
    expect(screen.getByRole("link", { name: "Privacidade" })).toHaveClass("text-white");
  });

  it("3. Renderiza aba de Círculo na rota /settings/circle", () => {
    renderSettings("/settings/circle");
    expect(screen.getByRole("link", { name: "Círculo de amigos" })).toHaveClass("text-white");
  });
});

