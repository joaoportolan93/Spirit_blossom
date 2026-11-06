import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Register } from "../pages/Register";
import * as authHook from "../hooks/useAuth";
import "../i18n";

describe("Register Component - Terms & Age Check (Onda 2)", () => {
  const mockRegister = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(authHook, "useAuth").mockReturnValue({
      user: null,
      loading: false,
      login: vi.fn(),
      register: mockRegister,
      logout: vi.fn(),
    });
  });

  it("1. Renderiza checkbox de termos de uso e política de privacidade", () => {
    render(
      <MemoryRouter>
        <Register />
      </MemoryRouter>
    );

    const checkbox = screen.getByTestId("register-terms");
    expect(checkbox).toBeInTheDocument();
    expect(checkbox).not.toBeChecked();
  });

  it("2. Impede envio e exibe erro se termos de uso não forem marcados", async () => {
    render(
      <MemoryRouter>
        <Register />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByTestId("register-email"), {
      target: { value: "test@example.com" },
    });
    fireEvent.change(screen.getByTestId("register-username"), {
      target: { value: "testuser" },
    });
    fireEvent.change(screen.getByTestId("register-birth-date"), {
      target: { value: "2000-01-01" },
    });
    fireEvent.change(screen.getByTestId("register-password"), {
      target: { value: "SenhaForte123!" },
    });
    fireEvent.change(screen.getByTestId("register-password-confirm"), {
      target: { value: "SenhaForte123!" },
    });

    // Submete sem marcar checkbox
    fireEvent.submit(screen.getByTestId("register-form"));

    await waitFor(() => {
      expect(screen.getByTestId("register-error")).toBeInTheDocument();
      expect(screen.getByTestId("register-error")).toHaveTextContent("Você deve aceitar os Termos de Uso");
    });
    expect(mockRegister).not.toHaveBeenCalled();
  });

  it("3. Submete com sucesso passando terms_accepted: true", async () => {
    mockRegister.mockResolvedValueOnce({ detail: "Conta criada" });

    render(
      <MemoryRouter>
        <Register />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByTestId("register-email"), {
      target: { value: "test@example.com" },
    });
    fireEvent.change(screen.getByTestId("register-username"), {
      target: { value: "testuser" },
    });
    fireEvent.change(screen.getByTestId("register-birth-date"), {
      target: { value: "2000-01-01" },
    });
    fireEvent.change(screen.getByTestId("register-password"), {
      target: { value: "SenhaForte123!" },
    });
    fireEvent.change(screen.getByTestId("register-password-confirm"), {
      target: { value: "SenhaForte123!" },
    });
    fireEvent.click(screen.getByTestId("register-terms"));

    fireEvent.submit(screen.getByTestId("register-form"));

    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalledWith(
        expect.objectContaining({
          email: "test@example.com",
          username: "testuser",
          terms_accepted: true,
        })
      );
    });
  });
});

