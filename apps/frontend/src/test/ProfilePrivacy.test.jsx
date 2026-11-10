import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { Profile } from "../pages/Profile";
import { SettingsPrivacy } from "../pages/settings/SettingsPrivacy";
import { api } from "../services/api";
import { AuthContext } from "../hooks/useAuth";
import "../i18n";

function renderWithAuth(ui, user = { username: "me" }, route = "/") {
  const authValue = {
    user,
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
  };

  return render(
    <AuthContext.Provider value={authValue}>
      <MemoryRouter initialEntries={[route]}>
        {ui}
      </MemoryRouter>
    </AuthContext.Provider>
  );
}

describe("Profile Privacy & Settings Privacy (Onda 3d)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. Exibe selo de conta privada no próprio perfil quando is_private = true", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/social/profile/me/")) {
        return Promise.resolve({
          data: {
            username: "me",
            followers_count: 5,
            following_count: 2,
            is_private: true,
            posts: [],
          },
        });
      }
      return Promise.resolve({ data: [] });
    });

    renderWithAuth(
      <Routes>
        <Route path="/profile/:username" element={<Profile />} />
        <Route path="/profile" element={<Profile />} />
      </Routes>,
      { username: "me" },
      "/profile/me"
    );

    await waitFor(() => {
      expect(screen.getByTestId("private-account-badge")).toBeInTheDocument();
      expect(screen.getByText("Conta Privada")).toBeInTheDocument();
    });
  });

  it("2. Não exibe selo de conta privada nem interruptor ao visualizar perfil de outro usuário", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/social/profile/other/")) {
        return Promise.resolve({
          data: {
            username: "other",
            is_private: true,
            followers_count: 10,
            following_count: 5,
            is_following: false,
            posts: [],
          },
        });
      }
      return Promise.resolve({ data: [] });
    });

    renderWithAuth(
      <Routes>
        <Route path="/profile/:username" element={<Profile />} />
      </Routes>,
      { username: "me" },
      "/profile/other"
    );

    await waitFor(() => {
      expect(screen.getByText("@other")).toBeInTheDocument();
      expect(screen.queryByTestId("private-account-badge")).not.toBeInTheDocument();
      expect(screen.queryByTestId("private-account-toggle")).not.toBeInTheDocument();
    });
  });

  it("3. SettingsPrivacy: exibe interruptor de privacidade e altera estado via PATCH", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/social/profile/me/")) {
        return Promise.resolve({
          data: {
            username: "me",
            is_private: true,
          },
        });
      }
      return Promise.resolve({ data: {} });
    });

    vi.spyOn(api, "patch").mockResolvedValueOnce({
      data: { username: "me", is_private: false },
    });

    renderWithAuth(<SettingsPrivacy />, { username: "me" }, "/settings/privacy");

    await waitFor(() => {
      const toggle = screen.getByTestId("private-account-toggle");
      expect(toggle).toBeInTheDocument();
      expect(toggle).toBeChecked();
    });

    const toggle = screen.getByTestId("private-account-toggle");
    fireEvent.click(toggle);

    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith("/api/users/profile/", { is_private: false });
      expect(toggle).not.toBeChecked();
      expect(screen.getByTestId("privacy-success")).toBeInTheDocument();
    });
  });

  it("4. SettingsPrivacy: exibe erro ao falhar PATCH", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/social/profile/me/")) {
        return Promise.resolve({
          data: {
            username: "me",
            is_private: false,
          },
        });
      }
      return Promise.resolve({ data: {} });
    });

    vi.spyOn(api, "patch").mockRejectedValueOnce(new Error("Falha na atualização"));

    renderWithAuth(<SettingsPrivacy />, { username: "me" }, "/settings/privacy");

    await waitFor(() => {
      expect(screen.getByTestId("private-account-toggle")).not.toBeChecked();
    });

    fireEvent.click(screen.getByTestId("private-account-toggle"));

    await waitFor(() => {
      expect(screen.getByTestId("privacy-error")).toHaveTextContent(
        "Erro ao atualizar privacidade da conta."
      );
    });
  });

  it("5. Profile: bloqueia e desbloqueia usuário com toast Desfazer", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/social/profile/outro/")) {
        return Promise.resolve({
          data: {
            username: "outro",
            followers_count: 10,
            following_count: 5,
            is_private: false,
          },
        });
      }
      return Promise.resolve({ data: [] });
    });
    vi.spyOn(api, "post").mockResolvedValue({ data: {} });
    vi.spyOn(api, "delete").mockResolvedValue({ data: {} });

    renderWithAuth(
      <Routes>
        <Route path="/profile/:username" element={<Profile />} />
      </Routes>,
      { username: "me" },
      "/profile/outro"
    );

    await waitFor(() => {
      expect(screen.getByTestId("block-button")).toBeInTheDocument();
      expect(screen.getByTestId("mute-button")).toBeInTheDocument();
    });

    // Clica em Bloquear
    fireEvent.click(screen.getByTestId("block-button"));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/social/block/outro/");
      expect(screen.getByText(/@outro foi bloqueado/)).toBeInTheDocument();
      expect(screen.getByTestId("undo-block-btn")).toBeInTheDocument();
    });

    // Clica em Desfazer
    fireEvent.click(screen.getByTestId("undo-block-btn"));

    await waitFor(() => {
      expect(api.delete).toHaveBeenCalledWith("/api/social/block/outro/");
    });
  });
});
