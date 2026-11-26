import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import App from "../App";
import { PostComposer } from "../components/PostComposer";
import { Explore } from "../pages/Explore";
import { Terms } from "../pages/Terms";
import { Privacy } from "../pages/Privacy";
import { Register } from "../pages/Register";
import { CompleteSignup } from "../pages/CompleteSignup";
import { SettingsPrivacy } from "../pages/settings/SettingsPrivacy";
import { AuthContext } from "../hooks/useAuth";
import * as authHook from "../hooks/useAuth";
import { api } from "../services/api";
import "../i18n";

describe("Onda 7b — Autocomplete, Filtro por Hashtag e Páginas Legais", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("1. PostComposer: autocomplete de @menções com debounce, setas e Enter", async () => {
    vi.useFakeTimers();
    const getSpy = vi.spyOn(api, "get").mockResolvedValueOnce({
      data: {
        results: [
          { username: "alice", avatar: null },
          { username: "aline", avatar: null },
        ],
      },
    });

    render(
      <MemoryRouter>
        <PostComposer />
      </MemoryRouter>
    );

    const textarea = screen.getByTestId("composer-textarea");
    fireEvent.change(textarea, { target: { value: "Oi @al", selectionStart: 6 } });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(260);
    });

    vi.useRealTimers();

    await waitFor(() => {
      expect(getSpy).toHaveBeenCalledWith("/api/users/search/?q=al&limit=5");
      expect(screen.getByTestId("mention-autocomplete")).toBeInTheDocument();
    });

    // Navega com ArrowDown para 'aline' e confirma com Enter
    fireEvent.keyDown(textarea, { key: "ArrowDown" });
    fireEvent.keyDown(textarea, { key: "Enter" });

    expect(textarea).toHaveValue("Oi @aline ");
    expect(screen.queryByTestId("mention-autocomplete")).not.toBeInTheDocument();
  });

  it("2. PostComposer modal: Escape fecha autocomplete antes de fechar modal", async () => {
    vi.useFakeTimers();
    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: { results: [{ username: "alice", avatar: null }] },
    });
    const onClose = vi.fn();

    render(
      <MemoryRouter>
        <PostComposer isOpen={true} onClose={onClose} />
      </MemoryRouter>
    );

    const textarea = screen.getByTestId("composer-textarea");
    fireEvent.change(textarea, { target: { value: "@al", selectionStart: 3 } });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(260);
    });
    vi.useRealTimers();

    await waitFor(() => {
      expect(screen.getByTestId("mention-autocomplete")).toBeInTheDocument();
    });

    fireEvent.keyDown(textarea, { key: "Escape" });
    expect(screen.queryByTestId("mention-autocomplete")).not.toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("3. Explore: filtra por ?hashtag=, exibe trending tags e limpa filtro", async () => {
    const getSpy = vi.spyOn(api, "get").mockImplementation((url) => {
      if (url === "/api/hashtags/trending/?limit=8") {
        return Promise.resolve({
          data: { results: [{ name: "lumen", posts_count: 3 }] },
        });
      }
      if (url === "/api/social/suggestions/?limit=5") {
        return Promise.resolve({ data: { results: [] } });
      }
      if (url === "/api/feed/explore/?hashtag=lumen") {
        return Promise.resolve({
          data: {
            items: [{ post_id: "p-tag-1", reason: "explore", cursor: "p-tag-1" }],
            next_cursor: null,
          },
        });
      }
      if (url === "/api/feed/explore/") {
        return Promise.resolve({
          data: { items: [], next_cursor: null },
        });
      }
      if (url === "/api/posts/p-tag-1/") {
        return Promise.resolve({
          data: {
            id: "p-tag-1",
            author: { username: "alice" },
            content_text: "Post com #lumen",
            created_at: new Date().toISOString(),
          },
        });
      }
      return Promise.resolve({ data: {} });
    });

    render(
      <AuthContext.Provider value={{ user: { username: "me" }, loading: false }}>
        <MemoryRouter initialEntries={["/explore?hashtag=lumen"]}>
          <Explore />
        </MemoryRouter>
      </AuthContext.Provider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("hashtag-filter-banner")).toHaveTextContent("#lumen");
      expect(screen.getByTestId("trending-tag-lumen")).toBeInTheDocument();
      expect(screen.getByText("Post com")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("clear-hashtag-filter"));

    await waitFor(() => {
      expect(getSpy).toHaveBeenCalledWith("/api/feed/explore/");
      expect(screen.queryByTestId("hashtag-filter-banner")).not.toBeInTheDocument();
    });
  });

  it("4. Páginas públicas Terms e Privacy renderizam conteúdo LGPD, Marco Civil e links", () => {
    render(
      <MemoryRouter initialEntries={["/terms"]}>
        <Routes>
          <Route path="/terms" element={<Terms />} />
          <Route path="/privacy" element={<Privacy />} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByTestId("terms-page")).toBeInTheDocument();
    expect(screen.getByText(/maiores de 18 anos/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("link", { name: "Política de Privacidade" }));
    expect(screen.getByTestId("privacy-page")).toBeInTheDocument();
    expect(screen.getAllByText(/Marco Civil/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/LGPD/i).length).toBeGreaterThanOrEqual(1);
  });

  it("5. Register, CompleteSignup e SettingsPrivacy exibem links legais e data de aceite", async () => {
    vi.spyOn(authHook, "useAuth").mockReturnValue({
      user: { username: "me" },
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      setUser: vi.fn(),
    });

    const { unmount } = render(
      <MemoryRouter>
        <Register />
      </MemoryRouter>
    );
    expect(screen.getByTestId("register-terms-link")).toHaveAttribute("href", "/terms");
    expect(screen.getByTestId("register-privacy-link")).toHaveAttribute("href", "/privacy");
    unmount();

    const { unmount: unmountComplete } = render(
      <MemoryRouter
        initialEntries={[
          {
            pathname: "/complete-signup",
            state: { onboarding_token: "tok", email: "a@b.com" },
          },
        ]}
      >
        <CompleteSignup />
      </MemoryRouter>
    );
    expect(screen.getByTestId("complete-terms-link")).toHaveAttribute("href", "/terms");
    expect(screen.getByTestId("complete-privacy-link")).toHaveAttribute("href", "/privacy");
    unmountComplete();

    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/social/profile/me/")) {
        return Promise.resolve({ data: { username: "me", is_private: false } });
      }
      if (url.includes("/api/users/settings/")) {
        return Promise.resolve({
          data: {
            show_likes_tab: true,
            terms_accepted_at: "2026-11-01T12:00:00Z",
          },
        });
      }
      return Promise.resolve({ data: {} });
    });

    render(
      <MemoryRouter>
        <SettingsPrivacy />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId("terms-accepted-status")).toHaveTextContent(/Aceite registrado em/i);
    });
  });

  it("6. PostComposer ignora @ com menos de 2 chars, suporta ArrowUp/Tab/clique e Terms/Privacy funcionam em EN", async () => {
    const i18n = (await import("../i18n")).default;
    vi.useFakeTimers();
    const getSpy = vi.spyOn(api, "get").mockResolvedValueOnce({
      data: {
        results: [
          { username: "alice", avatar: null },
          { username: "aline", avatar: null },
        ],
      },
    });

    const { unmount } = render(
      <MemoryRouter>
        <PostComposer />
      </MemoryRouter>
    );

    const textarea = screen.getByTestId("composer-textarea");
    // Apenas 1 char após @ não dispara busca (mínimo 2 chars na API)
    fireEvent.change(textarea, { target: { value: "@a", selectionStart: 2 } });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(260);
    });
    expect(getSpy).not.toHaveBeenCalled();

    // 2 chars dispara busca; ArrowUp seleciona última opção ('aline') e Tab insere
    fireEvent.change(textarea, { target: { value: "@al", selectionStart: 3 } });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(260);
    });
    vi.useRealTimers();

    await waitFor(() => {
      expect(screen.getByTestId("mention-autocomplete")).toBeInTheDocument();
    });
    fireEvent.keyDown(textarea, { key: "ArrowUp" });
    fireEvent.keyDown(textarea, { key: "Tab" });
    expect(textarea).toHaveValue("@aline ");
    unmount();

    // Renderiza Terms e Privacy em inglês (en)
    await act(async () => {
      await i18n.changeLanguage("en");
    });

    render(
      <MemoryRouter initialEntries={["/terms"]}>
        <Routes>
          <Route path="/terms" element={<Terms />} />
          <Route path="/privacy" element={<Privacy />} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByRole("heading", { name: "Terms of Use" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: "Privacy Policy" }));
    expect(screen.getByRole("heading", { name: "Privacy Policy" })).toBeInTheDocument();

    await act(async () => {
      await i18n.changeLanguage("pt-BR");
    });
  });

  it("7. PostComposer inline fecha dropdown de @menções ao publicar", async () => {
    vi.useFakeTimers();
    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: { results: [{ username: "alice", avatar: null }] },
    });
    const postSpy = vi.spyOn(api, "post").mockResolvedValueOnce({
      data: { id: "new-post-1", content_text: "Oi @al" },
    });

    render(
      <MemoryRouter>
        <PostComposer />
      </MemoryRouter>
    );

    const textarea = screen.getByTestId("composer-textarea");
    fireEvent.change(textarea, { target: { value: "Oi @al", selectionStart: 6 } });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(260);
    });
    vi.useRealTimers();

    await waitFor(() => {
      expect(screen.getByTestId("mention-autocomplete")).toBeInTheDocument();
    });

    fireEvent.submit(screen.getByTestId("publish-button").closest("form"));

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith("/api/posts/", {
        content_text: "Oi @al",
        visibility: "public",
      });
      expect(screen.queryByTestId("mention-autocomplete")).not.toBeInTheDocument();
    });
  });

  it("8. PostComposer aceita clique na opção de menção e fecha dropdown ao perder foco", async () => {
    vi.useFakeTimers();
    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: { results: [{ username: "alice", avatar: null }] },
    });

    render(
      <MemoryRouter>
        <PostComposer />
      </MemoryRouter>
    );

    const textarea = screen.getByTestId("composer-textarea");
    fireEvent.change(textarea, { target: { value: "Alô @al", selectionStart: 7 } });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(260);
    });
    vi.useRealTimers();

    await waitFor(() => {
      expect(screen.getByTestId("mention-option-alice")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("mention-option-alice"));
    expect(textarea).toHaveValue("Alô @alice ");
    expect(screen.queryByTestId("mention-autocomplete")).not.toBeInTheDocument();

    // Reabre e fecha ao perder foco
    vi.useFakeTimers();
    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: { results: [{ username: "alice", avatar: null }] },
    });
    fireEvent.change(textarea, { target: { value: "Alô @al", selectionStart: 7 } });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(260);
    });
    vi.useRealTimers();

    await waitFor(() => {
      expect(screen.getByTestId("mention-autocomplete")).toBeInTheDocument();
    });
    fireEvent.blur(textarea);
    expect(screen.queryByTestId("mention-autocomplete")).not.toBeInTheDocument();
  });

  it("9. Explore normaliza múltiplas # e Unicode NFD no parâmetro ?hashtag=", async () => {
    const getSpy = vi.spyOn(api, "get").mockResolvedValue({
      data: { items: [], next_cursor: null },
    });

    render(
      <MemoryRouter initialEntries={["/explore?hashtag=%23%23Cafe%CC%81"]}>
        <Explore />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId("hashtag-filter-banner")).toHaveTextContent("#café");
      expect(getSpy).toHaveBeenCalledWith("/api/feed/explore/?hashtag=caf%C3%A9");
    });
  });

  it("10. AppShell remove pl-60 para visitantes deslogados em /terms e aplica pl-60 autenticado", async () => {
    window.history.pushState({}, "", "/terms");
    vi.spyOn(api, "get").mockRejectedValue(new Error("unauth"));

    const { container, unmount } = render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId("terms-page")).toBeInTheDocument();
    });
    expect(container.querySelector(".pl-60")).toBeNull();
    unmount();

    window.history.pushState({}, "", "/");
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url === "/api/auth/me/") {
        return Promise.resolve({ status: 200, data: { username: "me" } });
      }
      if (url === "/api/notifications/") {
        return Promise.resolve({ status: 200, data: [] });
      }
      return Promise.resolve({ status: 200, data: [] });
    });

    const authRender = render(<App />);
    await waitFor(() => {
      expect(authRender.container.querySelector(".pl-60")).not.toBeNull();
    });
    authRender.unmount();
  });

  it("11. Renderiza /terms e /privacy sob os temas light, dark e oled com tipografia 65ch", async () => {
    for (const theme of ["light", "dark", "oled"]) {
      document.documentElement.setAttribute("data-theme", theme);

      const termsRender = render(
        <MemoryRouter>
          <Terms />
        </MemoryRouter>
      );
      expect(screen.getByTestId("terms-page")).toHaveClass("max-w-[65ch]");
      expect(screen.getByRole("article")).toBeInTheDocument();
      termsRender.unmount();

      const privacyRender = render(
        <MemoryRouter>
          <Privacy />
        </MemoryRouter>
      );
      expect(screen.getByTestId("privacy-page")).toHaveClass("max-w-[65ch]");
      expect(screen.getByRole("article")).toBeInTheDocument();
      privacyRender.unmount();
    }
  });
});
