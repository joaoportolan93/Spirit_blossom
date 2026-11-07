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

  it("4. Permite selecionar visibilidade circle e envia no payload da API", async () => {
    const onPostCreated = vi.fn();
    const mockPost = {
      id: "uuid-circle-1",
      content_text: "Mensagem restrita ao círculo",
      visibility: "circle",
      created_at: new Date().toISOString(),
    };

    vi.spyOn(api, "post").mockResolvedValueOnce({ data: mockPost });

    render(<Composer onPostCreated={onPostCreated} />);

    const textarea = screen.getByTestId("composer-textarea");
    const visibilitySelect = screen.getByTestId("visibility-select");
    const publishBtn = screen.getByTestId("publish-button");

    expect(visibilitySelect).toHaveValue("public");
    fireEvent.change(visibilitySelect, { target: { value: "circle" } });
    expect(visibilitySelect).toHaveValue("circle");

    fireEvent.change(textarea, { target: { value: "Mensagem restrita ao círculo" } });
    fireEvent.click(publishBtn);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/posts/", {
        content_text: "Mensagem restrita ao círculo",
        visibility: "circle",
      });
      expect(onPostCreated).toHaveBeenCalledWith(mockPost);
    });
  });

  it("5. Salva rascunho ao clicar no botão 'Salvar rascunho'", async () => {
    vi.spyOn(api, "post").mockResolvedValueOnce({
      data: { id: "draft-1", content_text: "Ideia para um post futuro" },
    });

    render(<Composer />);

    const textarea = screen.getByTestId("composer-textarea");
    const saveDraftBtn = screen.getByTestId("save-draft-button");

    expect(saveDraftBtn).toBeDisabled();

    fireEvent.change(textarea, { target: { value: "Ideia para um post futuro" } });
    expect(saveDraftBtn).toBeEnabled();

    fireEvent.click(saveDraftBtn);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/posts/drafts/", {
        content_text: "Ideia para um post futuro",
      });
      expect(screen.getByTestId("draft-success")).toHaveTextContent("Rascunho salvo!");
    });
  });

  it("6. Abre gaveta de rascunhos, carrega lista, seleciona e exclui um rascunho", async () => {
    const mockDrafts = [
      { id: "draft-10", content_text: "Rascunho anterior recuperado" },
      { id: "draft-11", content_text: "Segundo rascunho descartável" },
    ];

    vi.spyOn(api, "get").mockResolvedValueOnce({ data: mockDrafts });
    vi.spyOn(api, "delete").mockResolvedValueOnce({});

    render(<Composer />);

    const toggleBtn = screen.getByTestId("toggle-drafts-button");
    fireEvent.click(toggleBtn);

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("/api/posts/drafts/");
      expect(screen.getByTestId("drafts-drawer")).toBeInTheDocument();
      expect(screen.getByText("Rascunho anterior recuperado")).toBeInTheDocument();
      expect(screen.getByText("Segundo rascunho descartável")).toBeInTheDocument();
    });

    // Excluir segundo rascunho
    const deleteBtn = screen.getByTestId("delete-draft-draft-11");
    fireEvent.click(deleteBtn);

    await waitFor(() => {
      expect(api.delete).toHaveBeenCalledWith("/api/posts/drafts/draft-11/");
      expect(screen.queryByText("Segundo rascunho descartável")).not.toBeInTheDocument();
    });

    // Selecionar primeiro rascunho
    const draftItem = screen.getByTestId("draft-item-draft-10");
    fireEvent.click(draftItem);

    const textarea = screen.getByTestId("composer-textarea");
    expect(textarea).toHaveValue("Rascunho anterior recuperado");
    expect(screen.queryByTestId("drafts-drawer")).not.toBeInTheDocument();
  });
});
