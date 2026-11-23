import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SettingsAccount } from "../pages/settings/SettingsAccount";
import { AuthContext } from "../hooks/useAuth";
import "../i18n";

// ── Mocks de API ──────────────────────────────────────────────────────────────
const mockUpdateUserSettings = vi.fn();
const mockChangePassword = vi.fn();
const mockGetUserSettings = vi.fn();
const mockExportUserData = vi.fn();
const mockDeleteAccount = vi.fn();

vi.mock("../services/api", () => ({
  api: {
    get: vi.fn(),
    patch: vi.fn(),
  },
  updateUserSettings: (...args) => mockUpdateUserSettings(...args),
  changePassword: (...args) => mockChangePassword(...args),
  getUserSettings: (...args) => mockGetUserSettings(...args),
  exportUserData: (...args) => mockExportUserData(...args),
  deleteAccount: (...args) => mockDeleteAccount(...args),
}));

// Mock navigate
const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

// ── Auth context ──────────────────────────────────────────────────────────────
const mockSetUser = vi.fn();
const mockLogout = vi.fn();

const authValue = {
  user: { username: "alice", bio: "Bio antiga", avatar: "http://example.com/avatar.jpg" },
  loading: false,
  login: vi.fn(),
  logout: mockLogout,
  setUser: mockSetUser,
};

const oauthAuthValue = {
  user: {
    username: "alice_oauth",
    bio: "",
    avatar: null,
    has_usable_password: false,
  },
  loading: false,
  login: vi.fn(),
  logout: mockLogout,
  setUser: mockSetUser,
};

function renderComponent(overrideAuth = authValue) {
  return render(
    <AuthContext.Provider value={overrideAuth}>
      <MemoryRouter>
        <SettingsAccount />
      </MemoryRouter>
    </AuthContext.Provider>
  );
}

// ── Setup ─────────────────────────────────────────────────────────────────────
describe("SettingsAccount", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetUserSettings.mockResolvedValue({
      username: "alice",
      bio: "Minha bio",
      avatar: "http://example.com/avatar.jpg",
    });
    mockUpdateUserSettings.mockResolvedValue({
      username: "alice_new",
      bio: "Nova bio",
      avatar: "http://example.com/new.jpg",
    });
    mockChangePassword.mockResolvedValue({ detail: "Senha atualizada." });
    mockExportUserData.mockResolvedValue({ profile: { username: "alice" }, posts: [] });
    mockDeleteAccount.mockResolvedValue({});
    mockLogout.mockResolvedValue(undefined);
    global.URL.createObjectURL = vi.fn(() => "blob:http://localhost/preview-123");
    global.URL.revokeObjectURL = vi.fn();
  });

  // ── Testes de perfil (mantidos da Onda 5) ────────────────────────────────
  it("1. Renderiza campos de username, bio e foto existente", async () => {
    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("username-input")).toBeInTheDocument();
      expect(screen.getByTestId("display-name-input")).toBeInTheDocument();
      expect(screen.getByTestId("bio-input")).toBeInTheDocument();
      expect(screen.getByTestId("avatar-preview-img")).toBeInTheDocument();
      expect(screen.getByTestId("remove-avatar-btn")).toBeInTheDocument();
    });
  });

  it("2. Seleciona novo arquivo de avatar e exibe preview", async () => {
    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("avatar-upload-input")).toBeInTheDocument();
    });

    const file = new File(["fake-img"], "avatar.png", { type: "image/png" });
    const input = screen.getByTestId("avatar-upload-input");
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByTestId("avatar-preview-img")).toHaveAttribute(
        "src",
        "blob:http://localhost/preview-123"
      );
    });
  });

  it("3. Clicar em remover foto remove avatar atual", async () => {
    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("remove-avatar-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("remove-avatar-btn"));

    await waitFor(() => {
      expect(screen.queryByTestId("avatar-preview-img")).not.toBeInTheDocument();
      expect(screen.queryByTestId("remove-avatar-btn")).not.toBeInTheDocument();
    });
  });

  it("4. Salva perfil com sucesso", async () => {
    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("username-input")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("username-input"), {
      target: { value: "alice_new" },
    });
    fireEvent.change(screen.getByTestId("display-name-input"), {
      target: { value: "Alice Silva" },
    });
    fireEvent.change(screen.getByTestId("bio-input"), {
      target: { value: "Nova bio" },
    });
    fireEvent.click(screen.getByTestId("save-profile-btn"));

    await waitFor(() => {
      expect(mockUpdateUserSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          username: "alice_new",
          display_name: "Alice Silva",
          bio: "Nova bio",
        })
      );
      expect(screen.getByTestId("profile-success")).toBeInTheDocument();
    });
  });

  it("5. Exibe erro ao falhar atualização de perfil", async () => {
    mockUpdateUserSettings.mockRejectedValueOnce({
      response: { data: { username: ["Nome de usuário já em uso."] } },
    });
    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("save-profile-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("save-profile-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("profile-error")).toHaveTextContent(
        "Nome de usuário já em uso."
      );
    });
  });

  it("6. Exibe erro quando nova senha não coincide", async () => {
    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("current-password-input")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("current-password-input"), {
      target: { value: "senhaatual123" },
    });
    fireEvent.change(screen.getByTestId("new-password-input"), {
      target: { value: "novasenha123" },
    });
    fireEvent.change(screen.getByTestId("new-password-confirm-input"), {
      target: { value: "diferente456" },
    });
    fireEvent.click(screen.getByTestId("change-password-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("password-error")).toBeInTheDocument();
    });
  });

  it("7. Altera senha com sucesso", async () => {
    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("current-password-input")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("current-password-input"), {
      target: { value: "senhaatual123" },
    });
    fireEvent.change(screen.getByTestId("new-password-input"), {
      target: { value: "novasenha123" },
    });
    fireEvent.change(screen.getByTestId("new-password-confirm-input"), {
      target: { value: "novasenha123" },
    });
    fireEvent.click(screen.getByTestId("change-password-btn"));

    await waitFor(() => {
      expect(mockChangePassword).toHaveBeenCalledWith({
        current_password: "senhaatual123",
        new_password: "novasenha123",
        new_password_confirm: "novasenha123",
      });
      expect(screen.getByTestId("password-success")).toBeInTheDocument();
    });
  });

  // ── Testes Onda 6: Exportação de dados ───────────────────────────────────
  it("8. Botão 'Baixar meus dados' dispara download JSON", async () => {
    // Intercepta apenas o click do link <a> sem bloquear appendChild
    const clickSpy = vi.fn();
    const origCreate = document.createElement.bind(document);
    const createSpy = vi.spyOn(document, "createElement").mockImplementation((tag) => {
      const el = origCreate(tag);
      if (tag === "a") el.click = clickSpy;
      return el;
    });

    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("export-data-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("export-data-btn"));

    await waitFor(() => {
      expect(mockExportUserData).toHaveBeenCalledOnce();
      expect(clickSpy).toHaveBeenCalled();
    });

    createSpy.mockRestore();
  });

  it("9. Exibe estado de loading durante export", async () => {
    let resolveExport;
    mockExportUserData.mockReturnValueOnce(
      new Promise((r) => { resolveExport = r; })
    );

    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("export-data-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("export-data-btn"));

    // Botão desabilitado durante loading
    await waitFor(() => {
      expect(screen.getByTestId("export-data-btn")).toBeDisabled();
    });

    // Libera a promise
    resolveExport({ profile: {}, posts: [] });
  });

  it("10. Exibe erro quando export falha", async () => {
    mockExportUserData.mockRejectedValueOnce({
      response: { status: 500, data: { detail: "Internal Server Error" } },
    });

    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("export-data-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("export-data-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("export-error")).toBeInTheDocument();
    });
  });

  it("11. Botão 'Excluir minha conta' abre modal de confirmação", async () => {
    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("open-delete-modal-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("open-delete-modal-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("delete-confirm-password-input")).toBeInTheDocument();
    });
  });

  it("12. Fechar modal com Escape", async () => {
    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("open-delete-modal-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("open-delete-modal-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("delete-confirm-password-input")).toBeInTheDocument();
    });

    // Dispara Escape no dialog
    const dialog = screen.getByRole("dialog");
    fireEvent.keyDown(dialog, { key: "Escape" });

    await waitFor(() => {
      expect(screen.queryByTestId("delete-confirm-password-input")).not.toBeInTheDocument();
    });
  });

  it("13. Modal OAuth exige @username, não senha", async () => {
    mockGetUserSettings.mockResolvedValue({
      username: "alice_oauth",
      bio: "",
      avatar: null,
    });

    renderComponent(oauthAuthValue);
    await waitFor(() => {
      expect(screen.getByTestId("open-delete-modal-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("open-delete-modal-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("delete-confirm-username-input")).toBeInTheDocument();
      expect(screen.queryByTestId("delete-confirm-password-input")).not.toBeInTheDocument();
    });
  });

  it("14. Exclusão bem-sucedida chama logout e redireciona para /login", async () => {
    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("open-delete-modal-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("open-delete-modal-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("delete-confirm-password-input")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("delete-confirm-password-input"), {
      target: { value: "senhaatual123" },
    });
    fireEvent.click(screen.getByTestId("delete-modal-confirm-btn"));

    await waitFor(() => {
      expect(mockDeleteAccount).toHaveBeenCalledWith({
        current_password: "senhaatual123",
      });
      expect(mockLogout).toHaveBeenCalled();
      expect(mockNavigate).toHaveBeenCalledWith("/login", { replace: true });
    });
  });

  it("15. Senha errada exibe erro no modal", async () => {
    mockDeleteAccount.mockRejectedValueOnce({
      response: {
        status: 400,
        data: { current_password: ["Senha incorreta."] },
      },
    });

    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("open-delete-modal-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("open-delete-modal-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("delete-confirm-password-input")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("delete-confirm-password-input"), {
      target: { value: "senhaerrada" },
    });
    fireEvent.click(screen.getByTestId("delete-modal-confirm-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("delete-modal-error")).toHaveTextContent("Senha incorreta.");
    });
  });
});
