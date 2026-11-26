import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { AuthContext } from "../hooks/useAuth";
import { ReportModal } from "../components/ReportModal";
import { AdminLayout } from "../layouts/AdminLayout";
import { AdminDashboard } from "../pages/admin/AdminDashboard";
import { ModerationQueue } from "../pages/admin/ModerationQueue";
import { UserManagement } from "../pages/admin/UserManagement";
import { AdminModerationLogs } from "../pages/admin/AdminModerationLogs";
import { AdminSettings } from "../pages/admin/AdminSettings";
import { PostCard } from "../components/PostCard";
import { CommentItem } from "../components/CommentItem";
import { Profile } from "../pages/Profile";
import { Navbar } from "../components/Navbar";
import { api } from "../services/api";
import "../i18n";

function renderWithAuth(ui, { user = null, loading = false, route = "/admin" } = {}) {
  return render(
    <AuthContext.Provider value={{ user, loading, login: vi.fn(), logout: vi.fn() }}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </AuthContext.Provider>
  );
}

describe("Onda 8 — Denúncias, Moderação e Painel Admin", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("1. ReportModal envia denúncia e trata erro duplicado", async () => {
    const postSpy = vi
      .spyOn(api, "post")
      .mockResolvedValueOnce({ data: { id: "rep-1" } })
      .mockRejectedValueOnce({ response: { data: { detail: "Denúncia duplicada." } } });

    const onClose = vi.fn();
    const { unmount } = render(
      <ReportModal
        isOpen
        targetType="post"
        targetId="post-1"
        targetLabel="@alice"
        onClose={onClose}
      />
    );

    fireEvent.change(screen.getByTestId("report-reason-select"), {
      target: { value: "spam" },
    });
    fireEvent.change(screen.getByTestId("report-description-input"), {
      target: { value: "Propaganda" },
    });
    fireEvent.click(screen.getByTestId("report-submit-btn"));

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith("/api/reports/", {
        target_type: "post",
        target_id: "post-1",
        reason: "spam",
        description: "Propaganda",
      });
      expect(screen.getByTestId("report-success")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Fechar"));
    expect(onClose).toHaveBeenCalled();
    unmount();

    render(<ReportModal isOpen targetType="post" targetId="post-1" onClose={onClose} />);
    fireEvent.click(screen.getByTestId("report-submit-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("report-error")).toHaveTextContent("Denúncia duplicada.");
    });
  });

  it("2. PostCard, CommentItem e Profile abrem fluxo de denúncia para terceiros", async () => {
    const post = {
      id: "post-abc",
      content_text: "Post de terceiro",
      created_at: new Date().toISOString(),
      author: { username: "bob" },
      visibility: "public",
      likes_count: 0,
      bookmarks_count: 0,
      comments_count: 0,
    };

    renderWithAuth(<PostCard post={post} currentUser={{ username: "alice" }} />, {
      user: { username: "alice" },
      route: "/",
    });

    fireEvent.click(screen.getByTestId("post-menu-btn"));
    fireEvent.click(screen.getByTestId("post-report-btn"));
    expect(screen.getByTestId("report-modal")).toBeInTheDocument();
    cleanup();

    const comment = {
      id: "comm-1",
      content_text: "Comentário de bob",
      created_at: new Date().toISOString(),
      author: { id: "u-bob", username: "bob" },
      likes_count: 0,
      replies_count: 0,
    };
    renderWithAuth(
      <CommentItem
        comment={comment}
        postId="post-abc"
        currentUserId="u-alice"
        currentUser={{ id: "u-alice", username: "alice" }}
      />,
      { user: { id: "u-alice", username: "alice" }, route: "/" }
    );
    fireEvent.click(screen.getByTestId("comment-menu-btn-comm-1"));
    fireEvent.click(screen.getByTestId("report-comment-btn-comm-1"));
    expect(screen.getByTestId("report-modal")).toBeInTheDocument();
    cleanup();

    vi.spyOn(api, "get").mockResolvedValue({
      data: { id: "user-bob", username: "bob", posts: [] },
    });

    render(
      <AuthContext.Provider value={{ user: { username: "alice" }, loading: false, logout: vi.fn() }}>
        <MemoryRouter initialEntries={["/profile/bob"]}>
          <Routes>
            <Route path="/profile/:username" element={<Profile />} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("report-user-btn")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("report-user-btn"));
    expect(screen.getByTestId("report-modal")).toBeInTheDocument();
  });

  it("3. AdminLayout protege rotas contra anônimos e não-staff e Navbar exibe link para staff", () => {
    renderWithAuth(
      <Routes>
        <Route path="/admin" element={<AdminLayout><div>Painel</div></AdminLayout>} />
        <Route path="/" element={<div>Home</div>} />
      </Routes>,
      { user: { username: "comum", is_staff: false }, route: "/admin" }
    );
    expect(screen.getByText("Home")).toBeInTheDocument();
    cleanup();

    renderWithAuth(
      <Routes>
        <Route path="/admin" element={<AdminLayout><div>Painel</div></AdminLayout>} />
        <Route path="/login" element={<div>LoginPage</div>} />
      </Routes>,
      { user: null, route: "/admin" }
    );
    expect(screen.getByText("LoginPage")).toBeInTheDocument();
    cleanup();

    renderWithAuth(
      <Routes>
        <Route path="/admin" element={<AdminLayout><div>Painel Secreto</div></AdminLayout>} />
      </Routes>,
      { user: { username: "admin", is_staff: true }, route: "/admin" }
    );
    expect(screen.getByText("Painel Secreto")).toBeInTheDocument();
    cleanup();

    vi.spyOn(api, "get").mockResolvedValue({ data: { unread_count: 0 } });
    renderWithAuth(<Navbar />, { user: { username: "admin", is_staff: true }, route: "/" });
    expect(screen.getByText("Admin")).toBeInTheDocument();
    cleanup();

    renderWithAuth(
      <Routes>
        <Route path="/admin" element={<AdminLayout><div>Painel</div></AdminLayout>} />
      </Routes>,
      { user: null, loading: true, route: "/admin" }
    );
    expect(screen.getByTestId("admin-loading")).toBeInTheDocument();
  });

  it("4. AdminDashboard renderiza KPIs, série de 7 dias e trata erro", async () => {
    vi.spyOn(api, "get")
      .mockResolvedValueOnce({
        data: {
          kpis: {
            total_users: 42,
            pending_reports: 3,
            banned_users: 2,
            total_posts: 120,
            hidden_posts: 1,
            new_users_today: 5,
            new_posts_today: 12,
          },
          daily_stats: [
            { date: "2026-11-20", signups: 1, reports: 0, posts: 4 },
            { date: "2026-11-26", signups: 5, reports: 3, posts: 12 },
          ],
        },
      })
      .mockRejectedValueOnce(new Error("Falha stats"));

    render(<AdminDashboard />);
    await waitFor(() => {
      expect(screen.getByText("Painel Administrativo")).toBeInTheDocument();
      expect(screen.getByText("42")).toBeInTheDocument();
      expect(screen.getByText("120")).toBeInTheDocument();
    });
    cleanup();

    render(<AdminDashboard />);
    await waitFor(() => {
      expect(screen.getByText("Não foi possível carregar as estatísticas.")).toBeInTheDocument();
    });
    cleanup();

    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: { kpis: { total_users: 0, pending_reports: 0, banned_users: 0, total_posts: 0 }, daily_stats: [] },
    });
    render(<AdminDashboard />);
    await waitFor(() => {
      expect(screen.getByText("0.00%")).toBeInTheDocument();
    });
  });

  it("5. ModerationQueue lista denúncias, filtra por tipo e executa ações", async () => {
    vi.spyOn(api, "get").mockResolvedValue({
      data: [
        {
          id: "rep-10",
          target_type: "post",
          target_type_display: "Publicação",
          target_id: "post-99",
          reason: "spam",
          reason_display: "Spam",
          description: "Link suspeito",
          status: "pending",
          created_at: new Date().toISOString(),
          reporter: { id: "u1", username: "denunciante" },
          content: {
            type: "post",
            id: "post-99",
            content_text: "Compre seguidores agora",
            author: { id: "u2", username: "spammer" },
          },
        },
        {
          id: "rep-11",
          target_type: "user",
          target_type_display: "Usuário",
          target_id: "u3",
          reason: "harassment",
          reason_display: "Assédio",
          description: "",
          status: "pending",
          created_at: new Date().toISOString(),
          reporter: { id: "u1", username: "denunciante" },
          content: {
            type: "user",
            id: "u3",
            username: "ofensor",
            bio: "Bio do ofensor",
          },
        },
      ],
    });
    const postSpy = vi.spyOn(api, "post").mockResolvedValue({ data: { status: "resolved" } });

    render(<ModerationQueue />);

    await waitFor(() => {
      expect(screen.getAllByText("Compre seguidores agora").length).toBeGreaterThanOrEqual(1);
    });

    // Abre e cancela ConfirmModal
    fireEvent.click(screen.getByTestId("report-action-remove"));
    expect(screen.getByTestId("admin-confirm-modal")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Cancelar"));
    expect(screen.queryByTestId("admin-confirm-modal")).not.toBeInTheDocument();

    // Executa ocultar
    fireEvent.click(screen.getByTestId("report-action-hide"));
    fireEvent.click(screen.getByTestId("admin-confirm-btn"));

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith("/api/admin/reports/rep-10/action/", { action: "hide" });
    });

    // Filtra por Usuários, seleciona @ofensor e ignora rep-11
    fireEvent.click(screen.getByText("Usuários"));
    fireEvent.click(screen.getByText("@ofensor"));
    fireEvent.click(screen.getByTestId("report-action-ignore"));
    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith("/api/admin/reports/rep-11/action/", {
        action: "ignore",
      });
    });

    // Alterna para aba histórico
    fireEvent.click(screen.getByText("Histórico"));
    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("/api/admin/reports/?status=resolved");
    });
  });

  it("6. UserManagement permite inspecionar, banir, desbanir e excluir definitivamente", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/admin/users/u-active/")) {
        return Promise.resolve({
          data: {
            id: "u-active",
            username: "alvo1",
            email: "alvo1@example.com",
            status: "active",
            posts_count: 3,
            followers_count: 1,
            following_count: 2,
            reports_received: 0,
            date_joined: new Date().toISOString(),
          },
        });
      }
      return Promise.resolve({
        data: {
          results: [
            {
              id: "u-active",
              username: "alvo1",
              email: "alvo1@example.com",
              status: "active",
              date_joined: new Date().toISOString(),
            },
            {
              id: "u-banned",
              username: "banido1",
              email: "banido1@example.com",
              status: "suspended",
              appeal_days_remaining: 25,
              date_joined: new Date().toISOString(),
            },
          ],
          count: 2,
          page: 1,
          has_next: false,
        },
      });
    });
    const patchSpy = vi
      .spyOn(api, "patch")
      .mockResolvedValueOnce({
        data: {
          user: {
            id: "u-active",
            username: "alvo1",
            email: "alvo1@example.com",
            status: "suspended",
            date_joined: new Date().toISOString(),
          },
        },
      })
      .mockResolvedValueOnce({
        data: {
          user: {
            id: "u-banned",
            username: "banido1",
            email: "banido1@example.com",
            status: "active",
            date_joined: new Date().toISOString(),
          },
        },
      });
    const delSpy = vi.spyOn(api, "delete").mockResolvedValue({ data: {} });

    renderWithAuth(<UserManagement />, {
      user: { id: "admin-1", username: "admin", is_staff: true },
    });

    await waitFor(() => {
      expect(screen.getByTestId("ban-btn-alvo1")).toBeInTheDocument();
    });

    // Inspecionar alvo1
    fireEvent.click(screen.getAllByTitle("Inspecionar")[0]);
    await waitFor(() => {
      expect(screen.getByText("Detalhes da Conta")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByLabelText("Fechar"));

    // Banir alvo1 (testa validação de motivo vazio, duração, checkbox e sucesso)
    fireEvent.click(screen.getByTestId("ban-btn-alvo1"));
    fireEvent.submit(screen.getByTestId("ban-reason-input").closest("form"));
    expect(screen.getByText("O motivo do banimento é obrigatório.")).toBeInTheDocument();
    fireEvent.change(screen.getByTestId("ban-duration-select"), { target: { value: "7" } });
    fireEvent.click(screen.getByLabelText(/Preservar dados/i));
    fireEvent.change(screen.getByTestId("ban-reason-input"), { target: { value: "Abuso" } });
    fireEvent.click(screen.getByTestId("confirm-ban-btn"));

    await waitFor(() => {
      expect(patchSpy).toHaveBeenCalledWith("/api/admin/users/u-active/", {
        status: "suspended",
        reason: "Abuso",
        duration_days: 7,
        preserve_for_authorities: true,
      });
    });

    // Desbanir banido1
    fireEvent.click(screen.getByTestId("unban-btn-banido1"));
    fireEvent.click(screen.getByTestId("admin-confirm-btn"));
    await waitFor(() => {
      expect(patchSpy).toHaveBeenCalledWith("/api/admin/users/u-banned/", { status: "active" });
    });

    // Excluir definitivamente alvo1 (agora suspenso)
    await waitFor(() => {
      expect(screen.getByTestId("delete-user-btn-alvo1")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("delete-user-btn-alvo1"));
    fireEvent.change(screen.getByTestId("permanent-delete-username-input"), {
      target: { value: "@alvo1" },
    });
    fireEvent.click(screen.getByTestId("confirm-permanent-delete-btn"));

    await waitFor(() => {
      expect(delSpy).toHaveBeenCalledWith("/api/admin/users/u-active/", {
        data: { confirm_username: "alvo1" },
      });
    });

    // Busca, filtro por status e estado vazio + inspeção de conta suspensa
    fireEvent.change(screen.getByPlaceholderText("Buscar por username, e-mail ou nome..."), {
      target: { value: "alvo" },
    });
    fireEvent.click(screen.getByText("Buscar"));
    fireEvent.click(screen.getByText("Suspensos"));
    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith(expect.stringContaining("status=suspended"));
    });

    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/api/admin/users/u-banned/")) {
        return Promise.resolve({
          data: {
            id: "u-banned",
            username: "banido1",
            email: "banido1@example.com",
            status: "suspended",
            ban_reason: "Spam recorrente",
            banned_by: "admin",
            ban_expires_at: new Date().toISOString(),
            preserve_for_authorities: true,
            date_joined: new Date().toISOString(),
          },
        });
      }
      return Promise.resolve({ data: { results: [], count: 0, page: 1, has_next: false } });
    });
    fireEvent.click(screen.getByText("Desativados"));
    await waitFor(() => {
      expect(screen.getByText("Nenhum usuário encontrado.")).toBeInTheDocument();
    });
  });

  it("7. AdminModerationLogs e AdminSettings gerenciam logs e feature flags", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/moderation-logs/")) {
        return Promise.resolve({
          data: [
            {
              id: "log-1",
              action: "ban",
              action_display: "Usuário banido",
              target_type: "user",
              target_id: "u1",
              reason: "Spam",
              moderator_username: "admin",
              affected_username: "spammer",
              created_at: new Date().toISOString(),
            },
          ],
        });
      }
      return Promise.resolve({
        data: [
          {
            key: "dark_mode_v2",
            description: "Novo tema",
            is_enabled: false,
            admin_only: false,
            rollout_percentage: 100,
          },
        ],
      });
    });

    const patchSpy = vi.spyOn(api, "patch").mockResolvedValue({
      data: {
        key: "dark_mode_v2",
        description: "Novo tema",
        is_enabled: true,
        admin_only: false,
        rollout_percentage: 100,
      },
    });
    const postSpy = vi.spyOn(api, "post").mockResolvedValue({
      data: {
        key: "nova_flag",
        description: "Desc",
        is_enabled: false,
        admin_only: false,
        rollout_percentage: 100,
      },
    });
    const delSpy = vi.spyOn(api, "delete").mockResolvedValue({ data: {} });

    render(<AdminModerationLogs />);
    await waitFor(() => {
      expect(screen.getByText("Usuário banido")).toBeInTheDocument();
    });
    cleanup();

    vi.spyOn(api, "get").mockResolvedValueOnce({ data: [] });
    render(<AdminModerationLogs />);
    await waitFor(() => {
      expect(screen.getByText("Nenhum registro de moderação encontrado.")).toBeInTheDocument();
    });
    cleanup();

    render(<AdminSettings />);
    await waitFor(() => {
      expect(screen.getByTestId("toggle-flag-dark_mode_v2")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("toggle-flag-dark_mode_v2"));
    await waitFor(() => {
      expect(patchSpy).toHaveBeenCalledWith("/api/admin/feature-flags/dark_mode_v2/", {
        is_enabled: true,
      });
    });

    // Editar rollout % (cancela primeiro, depois salva) e alternar Admin Only
    fireEvent.click(screen.getByText("Rollout: 100%"));
    const pctInput = screen.getByDisplayValue("100");
    fireEvent.change(pctInput, { target: { value: "50" } });
    fireEvent.click(screen.getByText("Salvar"));
    await waitFor(() => {
      expect(patchSpy).toHaveBeenCalledWith("/api/admin/feature-flags/dark_mode_v2/", {
        rollout_percentage: 50,
      });
    });
    fireEvent.click(screen.getByText("Admin Only: OFF"));
    await waitFor(() => {
      expect(patchSpy).toHaveBeenCalledWith("/api/admin/feature-flags/dark_mode_v2/", {
        admin_only: true,
      });
    });

    fireEvent.click(screen.getByTestId("new-flag-btn"));
    fireEvent.change(screen.getByTestId("new-flag-key-input"), {
      target: { value: "nova_flag" },
    });
    fireEvent.change(screen.getByTestId("new-flag-desc-input"), {
      target: { value: "Nova descrição" },
    });
    fireEvent.click(screen.getByTestId("create-flag-submit"));
    await waitFor(() => {
      expect(postSpy).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByTestId("delete-flag-dark_mode_v2"));
    fireEvent.click(screen.getByTestId("admin-confirm-btn"));
    await waitFor(() => {
      expect(delSpy).toHaveBeenCalledWith("/api/admin/feature-flags/dark_mode_v2/");
    });
    cleanup();

    vi.spyOn(api, "get").mockRejectedValueOnce(new Error("err"));
    render(<AdminSettings />);
    await waitFor(() => {
      expect(screen.getByText("Erro ao carregar as feature flags.")).toBeInTheDocument();
    });
  });
});
