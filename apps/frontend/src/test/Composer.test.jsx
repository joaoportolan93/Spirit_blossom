import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Composer } from "../components/Composer";
import { api } from "../services/api";
import "../i18n";

describe("Composer Component (3 testes)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. Exibe contagem de caracteres restantes em tempo real", () => {
    render(<Composer />);

    const textarea = screen.getByTestId("composer-textarea");
    const charCount = screen.getByTestId("char-count");

    expect(charCount).toHaveTextContent("3000 caracteres restantes");

    fireEvent.change(textarea, { target: { value: "Olá Spirit Blossom!" } });
    expect(charCount).toHaveTextContent("2981 caracteres restantes");
  });

  it("2. Desabilita o botão de publicar quando vazio ou acima do limite de 3000", () => {
    render(<Composer />);

    const textarea = screen.getByTestId("composer-textarea");
    const publishBtn = screen.getByTestId("publish-button");

    // Vazio: desabilitado
    expect(publishBtn).toBeDisabled();

    // Com texto válido: habilitado
    fireEvent.change(textarea, { target: { value: "Post de teste válido" } });
    expect(publishBtn).toBeEnabled();

    // Acima de 3000 chars: desabilitado
    const longText = "a".repeat(3001);
    fireEvent.change(textarea, { target: { value: longText } });
    expect(publishBtn).toBeDisabled();
    expect(screen.getByTestId("char-count")).toHaveTextContent("Limite de caracteres excedido");
  });

  it("3. Submete o post chamando a API e limpa o textarea após sucesso", async () => {
    const onPostCreated = vi.fn();
    const mockPost = {
      id: "uuid-123",
      content_text: "Mensagem publicada com sucesso!",
      created_at: new Date().toISOString(),
    };

    vi.spyOn(api, "post").mockResolvedValueOnce({ data: mockPost });

    render(<Composer onPostCreated={onPostCreated} />);

    const textarea = screen.getByTestId("composer-textarea");
    const publishBtn = screen.getByTestId("publish-button");

    fireEvent.change(textarea, { target: { value: "Mensagem publicada com sucesso!" } });
    fireEvent.click(publishBtn);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/posts/", {
        content_text: "Mensagem publicada com sucesso!",
        visibility: "public",
      });
      expect(onPostCreated).toHaveBeenCalledWith(mockPost);
      expect(textarea).toHaveValue("");
    });
  });
});
