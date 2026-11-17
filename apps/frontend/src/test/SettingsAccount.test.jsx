import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SettingsAccount } from "../pages/settings/SettingsAccount";
import { AuthContext } from "../hooks/useAuth";
import "../i18n";

const mockUpdateUserSettings = vi.fn();
const mockChangePassword = vi.fn();
const mockGetUserSettings = vi.fn();

vi.mock("../services/api", () => ({
  api: {
    get: vi.fn(),
    patch: vi.fn(),
  },
  updateUserSettings: (...args) => mockUpdateUserSettings(...args),
  changePassword: (...args) => mockChangePassword(...args),
  getUserSettings: (...args) => mockGetUserSettings(...args),
}));

const mockSetUser = vi.fn();

const authValue = {
  user: { username: "alice", bio: "Bio antiga", avatar: "http://example.com/avatar.jpg" },
  loading: false,
  login: vi.fn(),
  logout: vi.fn(),
  setUser: mockSetUser,
};

function renderComponent() {
  return render(
    <AuthContext.Provider value={authValue}>
      <MemoryRouter>
        <SettingsAccount />
      </MemoryRouter>
    </AuthContext.Provider>
  );
}

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
    global.URL.createObjectURL = vi.fn(() => "blob:http://localhost/preview-123");
  });

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
});
