import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { PostComposer } from "../components/PostComposer";
import { PostCard } from "../components/PostCard";
import { PostPage } from "../pages/PostPage";
import CommentItem from "../components/CommentItem";
import { AuthContext } from "../hooks/useAuth";
import { api } from "../services/api";
import "../i18n";

function renderWithAuth(ui, user = { id: "u-1", username: "alice" }) {
  return render(
    <AuthContext.Provider value={{ user, loading: false }}>
      <MemoryRouter>{ui}</MemoryRouter>
    </AuthContext.Provider>
  );
}

describe("Mídia em Posts e Comentários (Imagem, GIF e Vídeo)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    if (!URL.createObjectURL) {
      URL.createObjectURL = vi.fn(() => "blob:mock-preview");
    } else {
      vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:mock-preview");
    }
    if (!URL.revokeObjectURL) {
      URL.revokeObjectURL = vi.fn();
    }
  });

  it("1. PostComposer: seleciona vídeo ou GIF pelo botão unificado e envia FormData", async () => {
    const postSpy = vi.spyOn(api, "post").mockResolvedValueOnce({
      data: { id: "p-gif", content_text: "", image_url: "/media/post_images/anim.gif" },
    });
    const onPostCreated = vi.fn();

    renderWithAuth(<PostComposer onPostCreated={onPostCreated} />);

    // Botão unificado "Adicionar mídias" aciona composer-image-input (múltiplo, aceita imagens e vídeos)
    const mediaInput = screen.getByTestId("composer-image-input");
    const imgClickSpy = vi.spyOn(mediaInput, "click");
    fireEvent.click(screen.getByTestId("composer-image-btn"));
    expect(imgClickSpy).toHaveBeenCalledTimes(1);
    expect(mediaInput.multiple).toBe(true);
    expect(mediaInput.accept).toContain("video/mp4");

    // Seleciona vídeo pelo input unificado, verifica preview e remove
    const vidFile = new File(["ftypisom"], "clip.mp4", { type: "video/mp4" });
    fireEvent.change(mediaInput, { target: { files: [vidFile] } });
    await waitFor(() => {
      expect(screen.getByTestId("media-preview-video")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("remove-media-btn"));
    expect(screen.queryByTestId("media-preview-container")).not.toBeInTheDocument();

    // Verifica que o botão GIF aciona seu input
    const gifBtn = screen.getByTestId("composer-gif-btn");
    const gifInput = screen.getByTestId("composer-gif-input");
    const clickSpy = vi.spyOn(gifInput, "click");
    fireEvent.click(gifBtn);
    expect(clickSpy).toHaveBeenCalledTimes(1);

    const gifFile = new File(["GIF89a"], "meme.gif", { type: "image/gif" });
    fireEvent.change(gifInput, { target: { files: [gifFile] } });

    await waitFor(() => {
      expect(screen.getByTestId("media-preview-image")).toBeInTheDocument();
    });

    // Permite publicar somente com mídia (sem texto)
    const publishBtn = screen.getByTestId("publish-button");
    expect(publishBtn).not.toBeDisabled();

    fireEvent.click(publishBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledTimes(1);
      const [url, body] = postSpy.mock.calls[0];
      expect(url).toBe("/api/posts/");
      expect(body instanceof FormData).toBe(true);
      expect(body.get("image")).toBe(gifFile);
      expect(onPostCreated).toHaveBeenCalled();
    });
  });

  it("2. PostComposer: rejeita imagem acima de 5 MB e vídeo acima de 50 MB", async () => {
    renderWithAuth(<PostComposer />);

    const mediaInput = screen.getByTestId("composer-image-input");
    const bigImg = new File(["x"], "huge.png", { type: "image/png" });
    Object.defineProperty(bigImg, "size", { value: 6 * 1024 * 1024 });
    fireEvent.change(mediaInput, { target: { files: [bigImg] } });

    await waitFor(() => {
      expect(screen.getByTestId("composer-error")).toHaveTextContent("5 MB");
    });

    const bigVid = new File(["v"], "huge.mp4", { type: "video/mp4" });
    Object.defineProperty(bigVid, "size", { value: 55 * 1024 * 1024 });
    fireEvent.change(mediaInput, { target: { files: [bigVid] } });

    await waitFor(() => {
      expect(screen.getByTestId("composer-error")).toHaveTextContent("50 MB");
    });
  });

  it("3. PostCard: renderiza imagem/GIF e vídeo enviados pela API", () => {
    renderWithAuth(
      <>
        <PostCard
          post={{
            id: "p-1",
            author: { username: "alice" },
            content_text: "Post com GIF",
            image_url: "http://localhost:8000/media/post_images/a.gif",
            likes_count: 0,
            comments_count: 0,
            bookmarks_count: 0,
          }}
        />
        <PostCard
          post={{
            id: "p-2",
            author: { username: "alice" },
            content_text: "Post com Vídeo",
            video_url: "http://localhost:8000/media/post_videos/v.mp4",
            likes_count: 0,
            comments_count: 0,
            bookmarks_count: 0,
          }}
        />
      </>
    );

    expect(screen.getByTestId("media-image")).toHaveAttribute(
      "src",
      "http://localhost:8000/media/post_images/a.gif"
    );
    expect(screen.getByTestId("media-video")).toHaveAttribute(
      "src",
      "http://localhost:8000/media/post_videos/v.mp4"
    );

    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    fireEvent.click(screen.getByTestId("media-image"));
    expect(openSpy).toHaveBeenCalledWith(
      "http://localhost:8000/media/post_images/a.gif",
      "_blank",
      "noopener,noreferrer"
    );
    fireEvent.click(screen.getByTestId("media-video"));
    openSpy.mockRestore();
  });

  it("4. PostPage e CommentItem: envia comentário raiz com GIF e renderiza mídia no comentário", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/comments/")) {
        return Promise.resolve({ data: { items: [], next_cursor: null } });
      }
      return Promise.resolve({
        data: {
          id: "post-1",
          author: { id: "u-1", username: "alice" },
          content_text: "Post alvo",
          likes_count: 0,
          comments_count: 0,
          bookmarks_count: 0,
        },
      });
    });

    const postSpy = vi.spyOn(api, "post").mockResolvedValueOnce({
      data: {
        id: "c-gif-1",
        author: { id: "u-1", username: "alice" },
        content_text: "",
        image_url: "/media/comment_images/meme.gif",
        likes_count: 0,
        replies_count: 0,
        created_at: new Date().toISOString(),
      },
    });

    render(
      <AuthContext.Provider value={{ user: { id: "u-1", username: "alice" }, loading: false }}>
        <MemoryRouter initialEntries={["/posts/post-1"]}>
          <Routes>
            <Route path="/posts/:id" element={<PostPage />} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("root-comment-gif-input")).toBeInTheDocument();
    });

    const rootImgSpy = vi.spyOn(screen.getByTestId("root-comment-image-input"), "click");
    fireEvent.click(screen.getByTestId("root-comment-image-btn"));
    expect(rootImgSpy).toHaveBeenCalled();

    const rootGifSpy = vi.spyOn(screen.getByTestId("root-comment-gif-input"), "click");
    fireEvent.click(screen.getByTestId("root-comment-gif-btn"));
    expect(rootGifSpy).toHaveBeenCalled();

    const rootVidSpy = vi.spyOn(screen.getByTestId("root-comment-video-input"), "click");
    fireEvent.click(screen.getByTestId("root-comment-video-btn"));
    expect(rootVidSpy).toHaveBeenCalled();

    const gifFile = new File(["GIF89a"], "react.gif", { type: "image/gif" });
    fireEvent.change(screen.getByTestId("root-comment-gif-input"), {
      target: { files: [gifFile] },
    });

    await waitFor(() => {
      expect(screen.getByTestId("media-preview-image")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("root-comment-submit"));

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledTimes(1);
      const [url, body] = postSpy.mock.calls[0];
      expect(url).toBe("/api/posts/post-1/comments/");
      expect(body instanceof FormData).toBe(true);
      expect(body.get("image")).toBe(gifFile);
      expect(screen.getByTestId("media-image")).toHaveAttribute(
        "src",
        "/media/comment_images/meme.gif"
      );
    });
  });

  it("5. CommentItem: resposta inline com imagem/GIF/vídeo envia payload com mídia", async () => {
    const onReplySubmit = vi.fn().mockResolvedValueOnce({ id: "r-1" });
    const setActiveReplyId = vi.fn();
    const comment = {
      id: "c-parent-1",
      author: { id: "u-2", username: "bob" },
      content_text: "Comentário pai",
      likes_count: 0,
      replies_count: 0,
      created_at: new Date().toISOString(),
    };

    renderWithAuth(
      <CommentItem
        comment={comment}
        postId="post-1"
        currentUserId="u-1"
        activeReplyId="c-parent-1"
        setActiveReplyId={setActiveReplyId}
        onReplySubmit={onReplySubmit}
      />
    );

    const imgBtn = screen.getByTestId("reply-image-btn-c-parent-1");
    const gifBtn = screen.getByTestId("reply-gif-btn-c-parent-1");
    const vidBtn = screen.getByTestId("reply-video-btn-c-parent-1");
    const imgInput = screen.getByTestId("reply-image-input-c-parent-1");
    const gifInput = screen.getByTestId("reply-gif-input-c-parent-1");
    const vidInput = screen.getByTestId("reply-video-input-c-parent-1");

    const s1 = vi.spyOn(imgInput, "click");
    const s2 = vi.spyOn(gifInput, "click");
    const s3 = vi.spyOn(vidInput, "click");
    fireEvent.click(imgBtn);
    fireEvent.click(gifBtn);
    fireEvent.click(vidBtn);
    expect(s1).toHaveBeenCalled();
    expect(s2).toHaveBeenCalled();
    expect(s3).toHaveBeenCalled();

    const file = new File(["GIF89a"], "reply.gif", { type: "image/gif" });
    fireEvent.change(gifInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByTestId("media-preview-image")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("reply-submit-btn-c-parent-1"));

    await waitFor(() => {
      expect(onReplySubmit).toHaveBeenCalledWith(
        { content_text: "", image: file, video: null },
        "c-parent-1"
      );
    });
  });
});
