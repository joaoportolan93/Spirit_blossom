import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { Profile } from "../pages/Profile";
import { api } from "../services/api";
import { AuthContext } from "../hooks/useAuth";
import "../i18n";

function renderProfileWithAuth(currentUser = { username: "me" }, initialRoute = "/profile/target") {
  const authValue = {
    user: currentUser,
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
  };

  return render(
    <AuthContext.Provider value={authValue}>
      <MemoryRouter initialEntries={[initialRoute]}>
        <Routes>
          <Route path="/profile/:username" element={<Profile />} />
          <Route path="/profile" element={<Profile />} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>
  );
}

describe("Profile Page & Mute Interactions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. Não exibe botão de silenciar no próprio perfil", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ data: [] });

    renderProfileWithAuth({ username: "me" }, "/profile/me");

    await waitFor(() => {
      expect(screen.getByText("@me")).toBeInTheDocument();
      expect(screen.queryByTestId("mute-button")).not.toBeInTheDocument();
    });
  });

  it("2. Exibe botão de silenciar em perfil de terceiro e permite alternar", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/social/profile/target/")) {
        return Promise.resolve({
          data: {
            username: "target",
            bio: "Bio do target",
            followers_count: 10,
            following_count: 5,
            is_following: false,
            is_muting: false,
            posts: [],
          },
        });
      }
      return Promise.resolve({ data: [] });
    });

    vi.spyOn(api, "post").mockResolvedValueOnce({ data: {} });
    vi.spyOn(api, "delete").mockResolvedValueOnce({ data: {} });

    renderProfileWithAuth({ username: "me" }, "/profile/target");

    await waitFor(() => {
      expect(screen.getByText("@target")).toBeInTheDocument();
    });

    const muteBtn = screen.getByTestId("mute-button");
    expect(muteBtn).toHaveTextContent("Silenciar");

    // Silenciar
    fireEvent.click(muteBtn);
    expect(muteBtn).toHaveTextContent("Desilenciar");

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/social/mute/target/");
    });

    // Desilenciar
    fireEvent.click(muteBtn);
    expect(muteBtn).toHaveTextContent("Silenciar");

    await waitFor(() => {
      expect(api.delete).toHaveBeenCalledWith("/api/social/mute/target/");
    });
  });

  it("3. Reverte botão de silenciar em caso de erro na requisição", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/social/profile/target/")) {
        return Promise.resolve({
          data: {
            username: "target",
            is_muting: false,
          },
        });
      }
      return Promise.resolve({ data: [] });
    });

    vi.spyOn(api, "post").mockRejectedValueOnce(new Error("Erro de rede"));

    renderProfileWithAuth({ username: "me" }, "/profile/target");

    await waitFor(() => {
      expect(screen.getByTestId("mute-button")).toBeInTheDocument();
    });

    const muteBtn = screen.getByTestId("mute-button");
    fireEvent.click(muteBtn);

    await waitFor(() => {
      expect(muteBtn).toHaveTextContent("Silenciar");
    });
  });

  it("4. Dono da conta vê aba de curtidas com selo privada quando show_likes_tab = false", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/social/profile/me/")) {
        return Promise.resolve({
          data: {
            username: "me",
            show_likes_tab: false,
            followers_count: 0,
            following_count: 0,
          },
        });
      }
      return Promise.resolve({ data: [] });
    });

    renderProfileWithAuth({ username: "me" }, "/profile/me");

    await waitFor(() => {
      expect(screen.getByTestId("tab-posts")).toBeInTheDocument();
      expect(screen.getByTestId("tab-likes")).toBeInTheDocument();
      expect(screen.getByTestId("likes-tab-private-badge")).toBeInTheDocument();
    });
  });

  it("5. Visitante NÃO vê aba de curtidas quando show_likes_tab = false", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/social/profile/target/")) {
        return Promise.resolve({
          data: {
            username: "target",
            show_likes_tab: false,
            followers_count: 1,
            following_count: 1,
          },
        });
      }
      return Promise.resolve({ data: [] });
    });

    renderProfileWithAuth({ username: "me" }, "/profile/target");

    await waitFor(() => {
      expect(screen.getByTestId("tab-posts")).toBeInTheDocument();
      expect(screen.queryByTestId("tab-likes")).not.toBeInTheDocument();
    });
  });

  it("6. Clicar na aba de curtidas requisita likes da API", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/social/profile/me/likes/")) {
        return Promise.resolve({
          data: [{ id: 101, content: "Post curtido", author: { username: "other" } }],
        });
      }
      if (url.includes("/api/social/profile/me/")) {
        return Promise.resolve({
          data: {
            username: "me",
            show_likes_tab: true,
            followers_count: 0,
            following_count: 0,
          },
        });
      }
      return Promise.resolve({ data: [] });
    });

    renderProfileWithAuth({ username: "me" }, "/profile/me");

    await waitFor(() => {
      expect(screen.getByTestId("tab-likes")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("tab-likes"));

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("/api/social/profile/me/likes/");
    });
  });

  it("7. FollowButton aciona handleFollowToggle e atualiza contagem de seguidores", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/social/profile/other/")) {
        return Promise.resolve({
          data: {
            username: "other",
            followers_count: 5,
            following_count: 2,
            is_following: false,
          },
        });
      }
      return Promise.resolve({ data: [] });
    });
    vi.spyOn(api, "post").mockResolvedValue({ data: { status: "active" } });

    renderProfileWithAuth({ username: "me" }, "/profile/other");

    await waitFor(() => {
      expect(screen.getByTestId("follow-button")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("follow-button"));

    await waitFor(() => {
      expect(screen.getByTestId("profile-stat-followers")).toHaveTextContent("6");
    });
  });
});
