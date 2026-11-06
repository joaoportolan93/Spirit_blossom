import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { CompleteSignup } from "../pages/CompleteSignup";
import * as authHook from "../hooks/useAuth";
import { api } from "../services/api";
import "../i18n";

describe("CompleteSignup Component - Google OAuth 18+ (Onda 2)", () => {
  const mockSetUser = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(authHook, "useAuth").mockReturnValue({
      user: null,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      setUser: mockSetUser,
    });
  });

  it("1. Exibe aviso de sessão expirada quando não há token", () => {
    render(
      <MemoryRouter initialEntries={["/complete-signup"]}>
        <Routes>
          <Route path="/complete-signup" element={<CompleteSignup />} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText("Sessão Expirada")).toBeInTheDocument();
  });

  it("2. Valida maioridade 18+, formato de username e aceite de termos", async () => {
    render(
      <MemoryRouter
        initialEntries={[
          {
            pathname: "/complete-signup",
            state: { onboarding_token: "test_token_123", email: "google@example.com" },
          },
        ]}
      >
        <Routes>
          <Route path="/complete-signup" element={<CompleteSignup />} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText("Conectado como: google@example.com")).toBeInTheDocument();

    // Tenta username com caracteres especiais
    fireEvent.change(screen.getByTestId("complete-username-input"), {
      target: { value: "user_invalido!" },
    });
    fireEvent.change(screen.getByTestId("complete-birth-date-input"), {
      target: { value: "2000-01-01" },
    });
    fireEvent.submit(screen.getByTestId("complete-signup-form"));

    await waitFor(() => {
      expect(screen.getByTestId("complete-signup-error")).toHaveTextContent(
        "apenas letras e números"
      );
    });

    // Tenta menor de 18 anos
    const underAgeYear = new Date().getFullYear() - 16;
    fireEvent.change(screen.getByTestId("complete-username-input"), {
      target: { value: "uservalido" },
    });
    fireEvent.change(screen.getByTestId("complete-birth-date-input"), {
      target: { value: `${underAgeYear}-01-01` },
    });
    fireEvent.submit(screen.getByTestId("complete-signup-form"));

    await waitFor(() => {
      expect(screen.getByTestId("complete-signup-error")).toHaveTextContent(
        "pelo menos 18 anos"
      );
    });

    // Idade 18+ mas sem marcar termos
    fireEvent.change(screen.getByTestId("complete-birth-date-input"), {
      target: { value: "2000-01-01" },
    });
    fireEvent.submit(screen.getByTestId("complete-signup-form"));

    await waitFor(() => {
      expect(screen.getByTestId("complete-signup-error")).toHaveTextContent(
        "Você deve aceitar os Termos de Uso"
      );
    });
  });

  it("3. Conclui cadastro com sucesso ao preencher todos os requisitos", async () => {
    const postSpy = vi.spyOn(api, "post").mockResolvedValueOnce({
      status: 201,
      data: { email: "google@example.com", detail: "Cadastro concluído." },
    });

    render(
      <MemoryRouter
        initialEntries={[
          {
            pathname: "/complete-signup",
            state: { onboarding_token: "valid_onboarding_token", email: "google@example.com" },
          },
        ]}
      >
        <Routes>
          <Route path="/complete-signup" element={<CompleteSignup />} />
        </Routes>
      </MemoryRouter>
    );

    fireEvent.change(screen.getByTestId("complete-username-input"), {
      target: { value: "googler123" },
    });
    fireEvent.change(screen.getByTestId("complete-birth-date-input"), {
      target: { value: "1998-05-20" },
    });
    fireEvent.click(screen.getByTestId("complete-terms-checkbox"));

    fireEvent.submit(screen.getByTestId("complete-signup-form"));

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith("/api/auth/google/complete/", {
        onboarding_token: "valid_onboarding_token",
        username: "googler123",
        birth_date: "1998-05-20",
        terms_accepted: true,
      });
      expect(mockSetUser).toHaveBeenCalledWith(
        expect.objectContaining({
          username: "googler123",
          birth_date: "1998-05-20",
          is_authenticated: true,
        })
      );
    });
  });
});

