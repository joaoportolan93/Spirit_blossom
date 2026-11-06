import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ForgotPassword } from "../pages/ForgotPassword";
import { api } from "../services/api";
import "../i18n";

describe("ForgotPassword Component (Onda 2)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. Renderiza campo de email e botão de envio", () => {
    render(
      <MemoryRouter>
        <ForgotPassword />
      </MemoryRouter>
    );

    expect(screen.getByTestId("forgot-email-input")).toBeInTheDocument();
    expect(screen.getByTestId("forgot-password-submit")).toBeInTheDocument();
  });

  it("2. Exibe mensagem uniforme anti-enumeração após envio com sucesso", async () => {
    const postSpy = vi.spyOn(api, "post").mockResolvedValueOnce({
      status: 200,
      data: { detail: "Solicitação processada." },
    });

    render(
      <MemoryRouter>
        <ForgotPassword />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByTestId("forgot-email-input"), {
      target: { value: "user@example.com" },
    });
    fireEvent.submit(screen.getByTestId("forgot-password-form"));

    await waitFor(() => {
      expect(screen.getByTestId("forgot-password-success")).toBeInTheDocument();
      expect(screen.getByTestId("forgot-password-success")).toHaveTextContent(
        "Se o e-mail estiver cadastrado em nossa base, um link de recuperação foi enviado"
      );
    });

    expect(postSpy).toHaveBeenCalledWith("/api/auth/password-reset/request/", {
      email: "user@example.com",
    });
  });

  it("3. Exibe erro 429 de throttle quando excedido", async () => {
    vi.spyOn(api, "post").mockRejectedValueOnce({
      response: {
        status: 429,
        data: { detail: "Request was throttled." },
      },
    });

    render(
      <MemoryRouter>
        <ForgotPassword />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByTestId("forgot-email-input"), {
      target: { value: "spam@example.com" },
    });
    fireEvent.submit(screen.getByTestId("forgot-password-form"));

    await waitFor(() => {
      expect(screen.getByTestId("forgot-password-error")).toBeInTheDocument();
      expect(screen.getByTestId("forgot-password-error")).toHaveTextContent("Muitas tentativas");
    });
  });
});

