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

  it("7. Opera em modo modal: fecha com botão X, backdrop e tecla Escape", () => {
    const onClose = vi.fn();
    const { rerender } = render(<Composer isOpen={true} onClose={onClose} />);

    expect(screen.getByRole("dialog")).toBeInTheDocument();

    // Fecha ao clicar no botão X
    const closeBtn = screen.getByLabelText("Fechar");
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalledTimes(1);

    // Fecha ao pressionar Escape
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(2);

    // Fecha ao clicar no backdrop do modal
    const dialog = screen.getByRole("dialog");
    fireEvent.click(dialog);
    expect(onClose).toHaveBeenCalledTimes(3);

    // Quando isOpen é falso, não renderiza nada
    rerender(<Composer isOpen={false} onClose={onClose} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("8. Abre e seleciona opção pelo dropdown customizado de visibilidade", () => {
    render(<Composer />);

    const triggerBtn = screen.getByRole("button", { name: /público/i });
    expect(triggerBtn).toBeInTheDocument();

    // Abre dropdown
    fireEvent.click(triggerBtn);
    const options = screen.getAllByRole("option", { name: /círculo de amigos/i });
    // options[0] é o <option> nativo do select oculto, options[1] é o <li> do dropdown customizado
    const customOption = options[1] || options[0];
    expect(customOption).toBeInTheDocument();

    // Seleciona Círculo
    fireEvent.click(customOption);
    expect(screen.getByTestId("visibility-select")).toHaveValue("circle");

    // Reabre e fecha clicando fora
    fireEvent.click(triggerBtn);
    expect(screen.getByRole("listbox")).toBeInTheDocument();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("9. Exibe warning em amarelo quando restam menos de 50 caracteres", () => {
    render(<Composer />);

    const textarea = screen.getByTestId("composer-textarea");
    const charCount = screen.getByTestId("char-count");

    // 2960 caracteres -> restam 40 (< 50)
    fireEvent.change(textarea, { target: { value: "a".repeat(2960) } });
    expect(charCount).toHaveClass("text-amber-400");
    expect(charCount).toHaveTextContent("40 caracteres restantes");

    // 2800 caracteres -> restam 200 (<= 300)
    fireEvent.change(textarea, { target: { value: "a".repeat(2800) } });
    expect(charCount).toHaveClass("text-zinc-500");
  });

  it("10. Exibe mensagem de estado vazio quando não há rascunhos", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({ data: [] });

    render(<Composer />);

    const toggleBtn = screen.getByTestId("toggle-drafts-button");
    fireEvent.click(toggleBtn);

    await waitFor(() => {
      expect(screen.getByTestId("empty-drafts-msg")).toBeInTheDocument();
    });
  });

  it("11. Exibe mensagem de erro quando API de publicação falha", async () => {
    vi.spyOn(api, "post").mockRejectedValueOnce({
      response: { data: { detail: "Erro de validação do servidor" } },
    });

    render(<Composer />);

    const textarea = screen.getByTestId("composer-textarea");
    const publishBtn = screen.getByTestId("publish-button");

    fireEvent.change(textarea, { target: { value: "Texto com erro" } });
    fireEvent.click(publishBtn);

    await waitFor(() => {
      expect(screen.getByTestId("composer-error")).toHaveTextContent("Erro de validação do servidor");
    });
  });
});
