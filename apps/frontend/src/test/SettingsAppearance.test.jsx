import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SettingsAppearance } from "../pages/settings/SettingsAppearance";
import { AuthContext } from "../hooks/useAuth";
import "../i18n";

const { mockUpdateUserSettings } = vi.hoisted(() => ({
  mockUpdateUserSettings: vi.fn().mockResolvedValue({ data: {} }),
}));

vi.mock("../services/api", () => ({
  updateUserSettings: mockUpdateUserSettings,
  getUserSettings: vi.fn().mockResolvedValue({ data: { theme: "dark", language: "pt-BR" } }),
}));

vi.mock("../utils/theme", () => ({
  applyTheme: vi.fn(),
  getInitialTheme: vi.fn().mockReturnValue("dark"),
}));

const authValue = {
  user: { username: "alice", theme: "dark", language: "pt-BR" },
  loading: false,
  login: vi.fn(),
  logout: vi.fn(),
};

function renderComponent() {
  return render(
    <AuthContext.Provider value={authValue}>
      <MemoryRouter>
        <SettingsAppearance />
      </MemoryRouter>
    </AuthContext.Provider>
  );
}

describe("SettingsAppearance", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("1. Renderiza 3 botões de tema", () => {
    renderComponent();
    expect(screen.getByTestId("theme-light-btn")).toBeInTheDocument();
    expect(screen.getByTestId("theme-dark-btn")).toBeInTheDocument();
    expect(screen.getByTestId("theme-oled-btn")).toBeInTheDocument();
  });

  it("2. Renderiza 2 botões de idioma", () => {
    renderComponent();
    expect(screen.getByTestId("lang-pt-btn")).toBeInTheDocument();
    expect(screen.getByTestId("lang-en-btn")).toBeInTheDocument();
  });

  it("3. Clicar em tema OLED chama updateUserSettings com theme=oled", async () => {
    renderComponent();
    fireEvent.click(screen.getByTestId("theme-oled-btn"));
    await waitFor(() => {
      expect(mockUpdateUserSettings).toHaveBeenCalledWith(
        expect.objectContaining({ theme: "oled" })
      );
    });
  });

  it("4. Clicar em idioma inglês chama updateUserSettings com language=en", async () => {
    renderComponent();
    fireEvent.click(screen.getByTestId("lang-en-btn"));
    await waitFor(() => {
      expect(mockUpdateUserSettings).toHaveBeenCalledWith(
        expect.objectContaining({ language: "en" })
      );
    });
  });
});
