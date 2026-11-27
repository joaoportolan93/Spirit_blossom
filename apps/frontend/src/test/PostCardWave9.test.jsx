/**
 * Onda 9 — Testes do PostCard: grid de mídia, ALT badge, lightbox e badge efêmero.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import PostCard from "../components/PostCard";
import { editPost } from "../services/api";
import "../i18n";

vi.mock("../services/api", () => ({
  api: {
    post: vi.fn(),
    delete: vi.fn(),
  },
  editPost: vi.fn(),
  deletePost: vi.fn(),
  muteUser: vi.fn(),
  blockUser: vi.fn(),
}));

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({ user: { username: "viewer", avatar: null } }),
}));

function makePost(overrides = {}) {
  return {
    id: "post-uuid-1",
    author: { username: "author1", display_name: "Author One", avatar: null },
    content_text: "Conteúdo do post",
    image_url: null,
    video_url: null,
    media: [],
    is_ephemeral: false,
    expires_at: null,
    visibility: "public",
    is_liked: false,
    is_bookmarked: false,
    likes_count: 0,
    comments_count: 0,
    bookmarks_count: 0,
    hidden_comments_count: 0,
    is_edited: false,
    edited_at: null,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

function makeMedia(count = 1) {
  return Array.from({ length: count }, (_, i) => ({
    id: `media-${i}`,
    url: `https://example.com/img${i}.jpg`,
    alt_text: i % 2 === 0 ? `Alt text ${i}` : "",
    order: i,
    width: 400,
    height: 300,
  }));
}

function renderCard(post, props = {}) {
  return render(
    <MemoryRouter>
      <PostCard post={post} {...props} />
    </MemoryRouter>,
  );
}

describe("PostCard — Onda 9 (grid de mídia + lightbox + badge efêmero)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. Sem media, o grid não é renderizado", () => {
    renderCard(makePost());
    expect(screen.queryByTestId("post-media-grid")).toBeNull();
  });

  it("2. Com 1 imagem, renderiza o grid com post-media-0", () => {
    renderCard(makePost({ media: makeMedia(1) }));
    expect(screen.getByTestId("post-media-grid")).toBeDefined();
    expect(screen.getByTestId("post-media-0")).toBeDefined();
  });

  it("3. Com 4 imagens, renderiza post-media-0 até post-media-3", () => {
    renderCard(makePost({ media: makeMedia(4) }));
    expect(screen.getByTestId("post-media-grid")).toBeDefined();
    for (let i = 0; i < 4; i++) {
      expect(screen.getByTestId(`post-media-${i}`)).toBeDefined();
    }
  });

  it("4. ALT badge aparece quando alt_text está preenchido", () => {
    // Mídia com alt_text no índice 0 (par = tem alt_text)
    renderCard(makePost({ media: makeMedia(2) }));
    expect(screen.getByTestId("post-alt-badge-0")).toBeDefined();
    // Índice 1 (ímpar = sem alt_text)
    expect(screen.queryByTestId("post-alt-badge-1")).toBeNull();
  });

  it("5. Clicar em imagem abre lightbox (post-lightbox)", async () => {
    renderCard(makePost({ media: makeMedia(2) }));
    expect(screen.queryByTestId("post-lightbox")).toBeNull();

    fireEvent.click(screen.getByTestId("post-media-0"));

    await waitFor(() => {
      expect(screen.getByTestId("post-lightbox")).toBeDefined();
    });
    expect(screen.getByTestId("post-lightbox").getAttribute("role")).toBe("dialog");
    expect(screen.getByTestId("post-lightbox").getAttribute("aria-modal")).toBe("true");
  });

  it("6. Lightbox fecha com tecla Escape", async () => {
    renderCard(makePost({ media: makeMedia(1) }));
    fireEvent.click(screen.getByTestId("post-media-0"));
    await waitFor(() => screen.getByTestId("post-lightbox"));

    fireEvent.keyDown(document, { key: "Escape" });

    await waitFor(() => {
      expect(screen.queryByTestId("post-lightbox")).toBeNull();
    });
  });

  it("7. Badge efêmero aparece quando is_ephemeral=true e expires_at no futuro", () => {
    const future = new Date(Date.now() + 18 * 60 * 60 * 1000).toISOString();
    renderCard(makePost({ is_ephemeral: true, expires_at: future }));
    expect(screen.getByTestId("post-ephemeral-badge")).toBeDefined();
  });

  it("8. Badge efêmero NÃO aparece quando is_ephemeral=false", () => {
    renderCard(makePost({ is_ephemeral: false, expires_at: null }));
    expect(screen.queryByTestId("post-ephemeral-badge")).toBeNull();
  });

  it("9. Badge efêmero mostra tempo em horas, não em segundos", () => {
    const future = new Date(Date.now() + 18 * 60 * 60 * 1000).toISOString();
    renderCard(makePost({ is_ephemeral: true, expires_at: future }));
    const badge = screen.getByTestId("post-ephemeral-badge");
    // Texto deve conter 'h' (horas) ou 'd' (dias), nunca 's' (segundos)
    expect(badge.textContent).toMatch(/\d+[hd]/);
    expect(badge.textContent).not.toMatch(/\d+s/);
  });

  it("10. Imagens têm loading='lazy', alt semântico/fallback e lightbox navega com setas", async () => {
    renderCard(makePost({ media: makeMedia(2) }));
    const img0 = screen.getByTestId("post-media-0");
    const img1 = screen.getByTestId("post-media-1");

    expect(img0.getAttribute("loading")).toBe("lazy");
    expect(img0.getAttribute("alt")).toBe("Alt text 0");
    expect(img1.getAttribute("alt")).toBe("Imagem anexada por @author1");

    // Clicar no badge ALT mostra texto alternativo
    fireEvent.click(screen.getByTestId("post-alt-badge-0"));
    expect(screen.getByRole("note")).toHaveTextContent("Alt text 0");

    // Abrir lightbox e navegar com ArrowRight / ArrowLeft
    fireEvent.click(img0);
    const dialog = await screen.findByTestId("post-lightbox");
    expect(dialog.querySelector("img")?.getAttribute("src")).toBe("https://example.com/img0.jpg");

    fireEvent.keyDown(document, { key: "ArrowRight" });
    await waitFor(() => {
      expect(dialog.querySelector("img")?.getAttribute("src")).toBe("https://example.com/img1.jpg");
    });

    fireEvent.keyDown(document, { key: "ArrowLeft" });
    await waitFor(() => {
      expect(dialog.querySelector("img")?.getAttribute("src")).toBe("https://example.com/img0.jpg");
    });
  });

  it("11. Modo de edição exibe imagens existentes e permite remover e adicionar", async () => {
    const media = makeMedia(2);
    const updatedPost = makePost({
      author: { username: "viewer", display_name: "Viewer", avatar: null },
      media: [media[1]],
    });
    editPost.mockResolvedValueOnce(updatedPost);

    renderCard(
      makePost({
        author: { username: "viewer", display_name: "Viewer", avatar: null },
        media,
      }),
      { currentUser: { username: "viewer" } },
    );

    expect(screen.getByTestId("post-media-grid").className).toContain("mt-3");

    fireEvent.click(screen.getByTestId("post-menu-btn"));
    fireEvent.click(screen.getByTestId("post-edit-btn"));

    // Imagens existentes aparecem no editor
    expect(screen.getByTestId("edit-media-grid")).toBeDefined();
    expect(screen.getByTestId("edit-add-media-btn")).toBeDefined();

    // Remove a primeira imagem e salva
    fireEvent.click(screen.getByTestId("edit-remove-existing-media-0"));
    fireEvent.click(screen.getByTestId("save-post-edit-btn"));

    await waitFor(() => {
      expect(editPost).toHaveBeenCalledOnce();
      const [postId, payload] = editPost.mock.calls[0];
      expect(postId).toBe("post-uuid-1");
      expect(payload).toBeInstanceOf(FormData);
      expect(payload.get("remove_media_ids")).toBe(JSON.stringify(["media-0"]));
    });
  });

  it("12. Grid com 2 e 3 imagens, abertura por teclado e botões do lightbox", async () => {
    const first = renderCard(makePost({ media: makeMedia(2) }));
    expect(screen.getByTestId("post-media-1")).toBeDefined();
    first.unmount();

    renderCard(makePost({ media: makeMedia(3) }));
    expect(screen.getByTestId("post-media-2")).toBeDefined();

    // Abre lightbox via Enter
    fireEvent.keyDown(screen.getByTestId("post-media-0"), { key: "Enter" });
    const dialog = await screen.findByTestId("post-lightbox");
    fireEvent.click(screen.getByLabelText(/Próxima imagem|Next image/i));
    await waitFor(() => {
      expect(dialog.querySelector("img")?.getAttribute("src")).toBe("https://example.com/img1.jpg");
    });
    fireEvent.click(screen.getByLabelText(/Imagem anterior|Previous image/i));
    await waitFor(() => {
      expect(dialog.querySelector("img")?.getAttribute("src")).toBe("https://example.com/img0.jpg");
    });
    fireEvent.click(screen.getByLabelText(/Fechar visualização|Close viewer/i));
    await waitFor(() => {
      expect(screen.queryByTestId("post-lightbox")).toBeNull();
    });
  });

  it("13. Edição inline adiciona novas imagens, edita ALT, valida erros e cancela", async () => {
    global.URL.createObjectURL = vi.fn(() => "blob:http://localhost/edit-preview");
    global.URL.revokeObjectURL = vi.fn();
    const media = makeMedia(1);
    editPost.mockRejectedValueOnce({ response: { data: { detail: "Falha ao salvar mídia" } } });

    renderCard(
      makePost({
        author: { username: "viewer", display_name: "Viewer", avatar: null },
        media,
      }),
      { currentUser: { username: "viewer" } },
    );

    fireEvent.click(screen.getByTestId("post-menu-btn"));
    fireEvent.click(screen.getByTestId("post-edit-btn"));
    fireEvent.click(screen.getByTestId("edit-add-media-btn"));

    const editInput = screen.getByTestId("edit-media-input");

    // Erro ao tentar misturar vídeo com imagem existente
    const videoFile = new File(["vid"], "clip.mp4", { type: "video/mp4" });
    fireEvent.change(editInput, { target: { files: [videoFile] } });
    expect(screen.getByTestId("post-edit-error")).toBeDefined();

    // Erro imagem > 5MB
    const bigFile = new File(["x"], "big.jpg", { type: "image/jpeg" });
    Object.defineProperty(bigFile, "size", { value: 6 * 1024 * 1024 });
    fireEvent.change(editInput, { target: { files: [bigFile] } });
    expect(screen.getByTestId("post-edit-error")).toBeDefined();

    // Adiciona nova imagem válida e edita ALTs
    const okFile = new File(["img"], "new.jpg", { type: "image/jpeg" });
    fireEvent.change(editInput, { target: { files: [okFile] } });
    await waitFor(() => screen.getByTestId("edit-remove-new-media-0"));

    const altInputs = screen.getAllByLabelText(/Texto alternativo|Alt text/i);
    fireEvent.change(altInputs[0], { target: { value: "ALT existente editado" } });
    fireEvent.change(altInputs[1], { target: { value: "ALT novo" } });

    // Tenta salvar e exibe erro da API
    fireEvent.click(screen.getByTestId("save-post-edit-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("post-edit-error")).toHaveTextContent("Falha ao salvar mídia");
    });

    // Remove imagem nova adicionada e cancela edição
    fireEvent.click(screen.getByTestId("edit-remove-new-media-0"));
    fireEvent.click(screen.getByTestId("cancel-post-edit-btn"));
    expect(screen.queryByTestId("edit-media-grid")).toBeNull();
  });

  it("14. Edição de post legado com imagem/vídeo permite substituir ou remover", async () => {
    global.URL.createObjectURL = vi.fn(() => "blob:http://localhost/legacy-edit");
    global.URL.revokeObjectURL = vi.fn();
    editPost.mockResolvedValueOnce(
      makePost({
        author: { username: "viewer", display_name: "Viewer", avatar: null },
        image_url: null,
        video_url: null,
      }),
    );

    renderCard(
      makePost({
        author: { username: "viewer", display_name: "Viewer", avatar: null },
        image_url: "https://example.com/old.gif",
      }),
      { currentUser: { username: "viewer" } },
    );

    fireEvent.click(screen.getByTestId("post-menu-btn"));
    fireEvent.click(screen.getByTestId("post-edit-btn"));
    expect(screen.getByTestId("edit-legacy-media")).toBeDefined();

    const editInput = screen.getByTestId("edit-media-input");
    // Substitui por vídeo
    const videoFile = new File(["v"], "new.mp4", { type: "video/mp4" });
    fireEvent.change(editInput, { target: { files: [videoFile] } });
    expect(screen.getByTestId("edit-legacy-media").querySelector("video")).not.toBeNull();

    // Remove mídia legada e envia
    fireEvent.click(screen.getByTestId("edit-remove-legacy-media"));
    fireEvent.click(screen.getByTestId("save-post-edit-btn"));

    await waitFor(() => {
      expect(editPost).toHaveBeenCalledOnce();
    });
  });

  it("15. Badge efêmero em dias (>=24h), expirado não mostra, Space abre lightbox e >4 imagens avisa erro", async () => {
    global.URL.createObjectURL = vi.fn(() => "blob:http://localhost/edit-limit");
    global.URL.revokeObjectURL = vi.fn();

    // >24h -> dias; já expirado -> sem badge
    const inTwoDays = new Date(Date.now() + 48 * 60 * 60 * 1000).toISOString();
    const first = renderCard(makePost({ is_ephemeral: true, expires_at: inTwoDays }));
    expect(screen.getByTestId("post-ephemeral-badge").textContent).toMatch(/2d/);
    first.unmount();

    const expired = new Date(Date.now() - 60 * 1000).toISOString();
    const second = renderCard(makePost({ is_ephemeral: true, expires_at: expired }));
    expect(screen.queryByTestId("post-ephemeral-badge")).toBeNull();
    second.unmount();

    // 4 imagens no edit + Space abre lightbox
    editPost.mockResolvedValueOnce(
      makePost({
        author: { username: "viewer", display_name: "Viewer", avatar: null },
        content_text: "Texto editado sem mexer na mídia",
        media: makeMedia(4),
      }),
    );
    renderCard(
      makePost({
        author: { username: "viewer", display_name: "Viewer", avatar: null },
        media: makeMedia(4),
      }),
      { currentUser: { username: "viewer" } },
    );

    fireEvent.keyDown(screen.getByTestId("post-media-0"), { key: " " });
    await screen.findByTestId("post-lightbox");
    fireEvent.keyDown(document, { key: "Escape" });

    fireEvent.click(screen.getByTestId("post-menu-btn"));
    fireEvent.click(screen.getByTestId("post-edit-btn"));
    const extraFile = new File(["img"], "extra.jpg", { type: "image/jpeg" });
    fireEvent.change(screen.getByTestId("edit-media-input"), { target: { files: [extraFile] } });
    expect(screen.getByTestId("post-edit-error")).toBeDefined();

    // Salva apenas alteração de texto (caminho JSON)
    fireEvent.change(screen.getByTestId("post-edit-textarea"), {
      target: { value: "Texto editado sem mexer na mídia" },
    });
    fireEvent.click(screen.getByTestId("save-post-edit-btn"));
    await waitFor(() => {
      expect(editPost).toHaveBeenCalledWith("post-uuid-1", "Texto editado sem mexer na mídia");
    });
  });
});
