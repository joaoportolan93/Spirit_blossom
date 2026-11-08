import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { Profile } from "../pages/Profile";
import { api } from "../services/api";
import { AuthContext } from "../hooks/useAuth";
import "../i18n";

function renderProfile(user = { username: "me" }, route = "/profile/me") {
  const authValue = {
    user,
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
  };

  return render(
    <AuthContext.Provider value={authValue}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/profile/:username" element={<Profile />} />
          <Route path="/profile" element={<Profile />} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>
  );
}

describe("Profile Privacy Toggle (Onda 3c)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. Exibe interruptor de conta privada no próprio perfil e lê estado inicial", async () => {
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

    renderProfile({ username: "me" }, "/profile/me");

    await waitFor(() => {
      const toggle = screen.getByTestId("private-account-toggle");
      expect(toggle).toBeInTheDocument();
      expect(toggle).toBeChecked();
      expect(screen.getByText("Conta Privada")).toBeInTheDocument();
    });
  });

  it("2. Alterna conta privada para pública via PATCH /api/users/profile/", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/social/profile/me/")) {
        return Promise.resolve({
          data: {
            username: "me",
            is_private: true,
            followers_count: 5,
            following_count: 2,
            posts: [],
          },
        });
      }
      return Promise.resolve({ data: [] });
    });

    vi.spyOn(api, "patch").mockResolvedValueOnce({
      data: { username: "me", is_private: false },
    });

    renderProfile({ username: "me" }, "/profile/me");

    await waitFor(() => {
      expect(screen.getByTestId("private-account-toggle")).toBeChecked();
    });

    const toggle = screen.getByTestId("private-account-toggle");
    fireEvent.click(toggle);

    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith("/api/users/profile/", { is_private: false });
      expect(toggle).not.toBeChecked();
    });
  });

  it("3. Não exibe interruptor de privacidade ao visualizar perfil de outro usuário", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/social/profile/other/")) {
        return Promise.resolve({
          data: {
            username: "other",
            is_private: false,
            followers_count: 10,
            following_count: 5,
            is_following: false,
            posts: [],
          },
        });
      }
      return Promise.resolve({ data: [] });
    });

    renderProfile({ username: "me" }, "/profile/other");

    await waitFor(() => {
      expect(screen.getByText("@other")).toBeInTheDocument();
      expect(screen.queryByTestId("private-account-toggle")).not.toBeInTheDocument();
    });
  });

  it("4. Exibe mensagem de erro se a requisição PATCH falhar", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/social/profile/me/")) {
        return Promise.resolve({
          data: {
            username: "me",
            is_private: false,
            followers_count: 0,
            following_count: 0,
            posts: [],
          },
        });
      }
      return Promise.resolve({ data: [] });
    });

    vi.spyOn(api, "patch").mockRejectedValueOnce(new Error("Falha na atualização"));

    renderProfile({ username: "me" }, "/profile/me");

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
});

