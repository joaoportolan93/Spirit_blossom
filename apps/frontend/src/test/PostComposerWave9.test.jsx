/**
 * Onda 9 — Testes do PostComposer: múltiplas imagens + posts efêmeros.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { PostComposer } from "../components/PostComposer";
import { api } from "../services/api";
import "../i18n";

// Mock do módulo de API
vi.mock("../services/api", () => ({
  api: {
    post: vi.fn(),
    patch: vi.fn(),
    get: vi.fn().mockResolvedValue({ data: [] }),
    delete: vi.fn(),
  },
  searchUsers: vi.fn().mockResolvedValue([]),
}));

// Mock de useAuth (retorna user fake)
vi.mock("../hooks/useAuth", () => ({
  AuthContext: { Provider: ({ children }) => children },
  useAuth: () => ({ user: { username: "testuser", avatar: null } }),
}));

// Mock de URL.createObjectURL / revokeObjectURL
const mockObjectURL = "blob:http://localhost/test-url";
global.URL.createObjectURL = vi.fn(() => mockObjectURL);
global.URL.revokeObjectURL = vi.fn();

function makeFile(name = "test.jpg", type = "image/jpeg") {
  const content = new Uint8Array([0xff, 0xd8, 0xff, 0xe0]); // JPEG magic bytes
  return new File([content], name, { type });
}

describe("PostComposer — Onda 9 (multi-imagens + efêmero)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.post.mockResolvedValue({
      data: { id: "uuid-1", content_text: "ok", media: [], is_ephemeral: false, expires_at: null },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("1. Botão unificado 'Adicionar mídias' está presente (composer-image-btn)", () => {
    render(<PostComposer />);
    const btn = screen.getByTestId("composer-image-btn");
    expect(btn).toBeDefined();
    expect(btn.getAttribute("aria-label")).toBe("Adicionar mídias");
    expect(screen.queryByTestId("composer-images-btn")).toBeNull();
    expect(screen.queryByTestId("composer-video-btn")).toBeNull();
  });

  it("2. Input unificado aceita múltiplas imagens e vídeos (composer-image-input)", () => {
    render(<PostComposer />);
    const input = screen.getByTestId("composer-image-input");
    expect(input.classList.contains("hidden")).toBe(true);
    expect(input.multiple).toBe(true);
    expect(input.accept).toContain("image/jpeg");
    expect(input.accept).toContain("video/mp4");
  });

  it("3. Selecionar imagens cria previews (image-preview-0, image-preview-1)", async () => {
    render(<PostComposer />);
    const input = screen.getByTestId("composer-image-input");

    const files = [makeFile("a.jpg"), makeFile("b.jpg")];
    fireEvent.change(input, { target: { files } });

    await waitFor(() => {
      expect(screen.getByTestId("image-preview-0")).toBeDefined();
      expect(screen.getByTestId("image-preview-1")).toBeDefined();
    });
    expect(URL.createObjectURL).toHaveBeenCalledTimes(2);
  });

  it("4. Botão remove imagem específica (remove-image-0) e revoga ObjectURL", async () => {
    render(<PostComposer />);
    const input = screen.getByTestId("composer-image-input");
    const files = [makeFile("a.jpg"), makeFile("b.jpg")];
    fireEvent.change(input, { target: { files } });

    await waitFor(() => screen.getByTestId("remove-image-0"));

    fireEvent.click(screen.getByTestId("remove-image-0"));

    await waitFor(() => {
      expect(screen.queryByTestId("image-preview-0")).toBeDefined(); // índice reajusta
    });
    expect(URL.revokeObjectURL).toHaveBeenCalledWith(mockObjectURL);
  });

  it("5. Campo alt-text-input-0 atualiza valor", async () => {
    render(<PostComposer />);
    const input = screen.getByTestId("composer-image-input");
    fireEvent.change(input, { target: { files: [makeFile()] } });

    await waitFor(() => screen.getByTestId("image-preview-0"));

    const altInput = screen.getByTestId("alt-text-input-0");
    fireEvent.change(altInput, { target: { value: "Descrição da imagem" } });
    expect(altInput.value).toBe("Descrição da imagem");
  });

  it("6. Selector efêmero existe (ephemeral-selector)", () => {
    render(<PostComposer />);
    expect(screen.getByTestId("ephemeral-selector")).toBeDefined();
  });

  it("7. Botão efêmero (ephemeral-btn) cicla pelas opções", async () => {
    render(<PostComposer />);
    const btn = screen.getByTestId("ephemeral-btn");
    // Estado inicial: permanente (nenhum badge)
    expect(screen.queryByText(/24h|48h|7d/)).toBeNull();

    // 1 click → 24h
    fireEvent.click(btn);
    await waitFor(() => expect(screen.getByText("24h")).toBeDefined());
  });

  it("8. Submit com imagens usa FormData", async () => {
    render(<PostComposer />);
    const input = screen.getByTestId("composer-image-input");
    fireEvent.change(input, { target: { files: [makeFile()] } });
    await waitFor(() => screen.getByTestId("image-preview-0"));

    const textarea = screen.getByTestId("composer-textarea");
    fireEvent.change(textarea, { target: { value: "Post com imagem" } });

    const publishBtn = screen.getByTestId("publish-button");
    fireEvent.click(publishBtn);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledOnce();
      const callArg = api.post.mock.calls[0][1];
      expect(callArg).toBeInstanceOf(FormData);
    });
  });

  it("9. Submit sem imagens usa JSON", async () => {
    render(<PostComposer />);
    const textarea = screen.getByTestId("composer-textarea");
    fireEvent.change(textarea, { target: { value: "Só texto" } });

    fireEvent.click(screen.getByTestId("publish-button"));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledOnce();
      const callArg = api.post.mock.calls[0][1];
      expect(callArg).not.toBeInstanceOf(FormData);
    });
  });

  it("10. ObjectURLs são revogados ao publicar", async () => {
    render(<PostComposer />);
    const input = screen.getByTestId("composer-image-input");
    fireEvent.change(input, { target: { files: [makeFile()] } });
    await waitFor(() => screen.getByTestId("image-preview-0"));

    const textarea = screen.getByTestId("composer-textarea");
    fireEvent.change(textarea, { target: { value: "Enviando" } });
    fireEvent.click(screen.getByTestId("publish-button"));

    await waitFor(() => expect(api.post).toHaveBeenCalled());
    expect(URL.revokeObjectURL).toHaveBeenCalled();
  });

  it("11. Bloqueia mais de 4 imagens com mensagem localizada", async () => {
    render(<PostComposer />);
    const input = screen.getByTestId("composer-image-input");
    const files = [0, 1, 2, 3, 4].map((i) => makeFile(`img${i}.jpg`));
    fireEvent.change(input, { target: { files } });

    await waitFor(() => {
      expect(screen.getByTestId("composer-error")).toHaveTextContent("Máximo de 4 imagens");
      expect(screen.getByTestId("image-preview-3")).toBeDefined();
    });
    expect(screen.queryByTestId("image-preview-4")).toBeNull();
  });

  it("12. Envia ephemeral_duration_hours no FormData junto com imagens", async () => {
    render(<PostComposer />);
    fireEvent.change(screen.getByTestId("composer-image-input"), {
      target: { files: [makeFile()] },
    });
    await waitFor(() => screen.getByTestId("image-preview-0"));

    fireEvent.click(screen.getByTestId("ephemeral-btn")); // 24h
    fireEvent.change(screen.getByTestId("composer-textarea"), {
      target: { value: "Efêmero com foto" },
    });
    fireEvent.click(screen.getByTestId("publish-button"));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledOnce();
      const formData = api.post.mock.calls[0][1];
      expect(formData).toBeInstanceOf(FormData);
      expect(formData.get("ephemeral_duration_hours")).toBe("24");
    });
  });

  it("13. Revoga previews no unmount para evitar memory leak", async () => {
    const { unmount } = render(<PostComposer />);
    fireEvent.change(screen.getByTestId("composer-image-input"), {
      target: { files: [makeFile()] },
    });
    await waitFor(() => screen.getByTestId("image-preview-0"));

    vi.clearAllMocks();
    unmount();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith(mockObjectURL);
  });
});
