import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SettingsNotifications } from "../pages/settings/SettingsNotifications";
import { AuthContext } from "../hooks/useAuth";
import "../i18n";

const { mockUpdateUserSettings } = vi.hoisted(() => ({
  mockUpdateUserSettings: vi.fn().mockResolvedValue({ data: {} }),
}));

vi.mock("../services/api", () => ({
  updateUserSettings: mockUpdateUserSettings,
  getUserSettings: vi.fn().mockResolvedValue({
    data: {
      notify_likes: true,
      notify_comments: true,
      notify_follows: true,
      notify_mentions: true,
    },
  }),
}));

const authValue = {
  user: { username: "alice" },
  loading: false,
  login: vi.fn(),
  logout: vi.fn(),
};

function renderComponent() {
  return render(
    <AuthContext.Provider value={authValue}>
      <MemoryRouter>
        <SettingsNotifications />
      </MemoryRouter>
    </AuthContext.Provider>
  );
}

describe("SettingsNotifications", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. Renderiza 4 toggles de notificação", async () => {
    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("notify-likes-toggle")).toBeInTheDocument();
      expect(screen.getByTestId("notify-comments-toggle")).toBeInTheDocument();
      expect(screen.getByTestId("notify-follows-toggle")).toBeInTheDocument();
      expect(screen.getByTestId("notify-mentions-toggle")).toBeInTheDocument();
    });
  });

  it("2. Clicar em toggle chama updateUserSettings", async () => {
    renderComponent();
    await waitFor(() => screen.getByTestId("notify-likes-toggle"));

    const toggle = screen.getByTestId("notify-likes-toggle");
    fireEvent.click(toggle);

    await waitFor(() => {
      expect(mockUpdateUserSettings).toHaveBeenCalledWith(
        expect.objectContaining({ notify_likes: expect.any(Boolean) })
      );
    });
  });
});
