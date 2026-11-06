import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ResetPassword } from "../pages/ResetPassword";
import { api } from "../services/api";
import "../i18n";

describe("ResetPassword Component (Onda 2)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.location.hash = "";
  });

  it("1. Alerta quando token não está presente no fragmento", () => {
    window.location.hash = "";
    render(
      <MemoryRouter>
        <ResetPassword />
      </MemoryRouter>
    );

    expect(screen.getByTestId("reset-password-error")).toHaveTextContent(
      "Token de recuperação ausente ou link incompleto"
    );
  });

  it("2. Rejeita senhas divergentes ou com menos de 8 caracteres", async () => {
    window.location.hash = "#token=token123xyz";

    render(
      <MemoryRouter>
        <ResetPassword />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByTestId("reset-new-password-input"), {
      target: { value: "curta" },
    });
    fireEvent.change(screen.getByTestId("reset-new-password-confirm-input"), {
      target: { value: "curta" },
    });
    fireEvent.submit(screen.getByTestId("reset-password-form"));

    await waitFor(() => {
      expect(screen.getByTestId("reset-password-error")).toHaveTextContent(
        "A senha deve ter no mínimo 8 caracteres."
      );
    });

    fireEvent.change(screen.getByTestId("reset-new-password-input"), {
      target: { value: "NovaSenhaForte123!" },
    });
    fireEvent.change(screen.getByTestId("reset-new-password-confirm-input"), {
      target: { value: "SenhaDiferente123!" },
    });
    fireEvent.submit(screen.getByTestId("reset-password-form"));

    await waitFor(() => {
      expect(screen.getByTestId("reset-password-error")).toHaveTextContent(
        "As senhas não conferem."
      );
    });
  });

  it("3. Envia formulário com sucesso quando senhas são válidas", async () => {
    window.location.hash = "#token=token_valido_999";
    const postSpy = vi.spyOn(api, "post").mockResolvedValueOnce({
      status: 200,
      data: { detail: "Senha redefinida com sucesso." },
    });

    render(
      <MemoryRouter>
        <ResetPassword />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByTestId("reset-new-password-input"), {
      target: { value: "NovaSenhaForte123!@" },
    });
    fireEvent.change(screen.getByTestId("reset-new-password-confirm-input"), {
      target: { value: "NovaSenhaForte123!@" },
    });
    fireEvent.submit(screen.getByTestId("reset-password-form"));

    await waitFor(() => {
      expect(screen.getByTestId("reset-password-success")).toBeInTheDocument();
      expect(screen.getByTestId("reset-password-success")).toHaveTextContent(
        "Sua senha foi redefinida com sucesso!"
      );
    });

    expect(postSpy).toHaveBeenCalledWith("/api/auth/password-reset/confirm/", {
      token: "token_valido_999",
      new_password: "NovaSenhaForte123!@",
      new_password_confirm: "NovaSenhaForte123!@",
    });
  });
});

