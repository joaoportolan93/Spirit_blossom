import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { RichText } from "../components/RichText";
import { PostCard } from "../components/PostCard";
import CommentItem from "../components/CommentItem";
import "../i18n";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

function renderWithRouter(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("RichText Component (Onda 7b)", () => {
  it("1. Transforma @menções e #hashtags em links seguros", () => {
    renderWithRouter(
      <p>
        <RichText text="Olá @Alice e @Bob99, curtam #SpiritBlossom e #Ação!" />
      </p>
    );

    const aliceLink = screen.getByRole("link", { name: "@Alice" });
    expect(aliceLink).toHaveAttribute("href", "/profile/alice");

    const bobLink = screen.getByRole("link", { name: "@Bob99" });
    expect(bobLink).toHaveAttribute("href", "/profile/bob99");

    const tag1 = screen.getByRole("link", { name: "#SpiritBlossom" });
    expect(tag1).toHaveAttribute("href", "/explore?hashtag=spiritblossom");

    const tag2 = screen.getByRole("link", { name: "#Ação" });
    expect(tag2).toHaveAttribute("href", "/explore?hashtag=a%C3%A7%C3%A3o");
  });

  it("2. Ignora e-mails, URLs com fragmentos/@ e tags puramente numéricas", () => {
    renderWithRouter(
      <p>
        <RichText text="Email user@domain.com URL https://example.com/@alice#section #123 #2026" />
      </p>
    );

    expect(screen.queryAllByRole("link")).toHaveLength(0);
    expect(screen.getByText(/user@domain\.com/)).toBeInTheDocument();
    expect(screen.getByText(/https:\/\/example\.com\/@alice#section/)).toBeInTheDocument();
  });

  it("3. Previne XSS renderizando HTML como texto puro", () => {
    renderWithRouter(
      <p data-testid="xss-box">
        <RichText text='<script>alert("xss")</script> @alice' />
      </p>
    );

    const box = screen.getByTestId("xss-box");
    expect(box.querySelector("script")).toBeNull();
    expect(box).toHaveTextContent('<script>alert("xss")</script> @alice');
    expect(screen.getByRole("link", { name: "@alice" })).toHaveAttribute("href", "/profile/alice");
  });

  it("4. Integra RichText no PostCard para @menções e #hashtags", () => {
    const post = {
      id: "p1",
      content_text: "Conversa com @maria sobre #Lumen",
      created_at: new Date().toISOString(),
      author: { username: "joao" },
    };

    renderWithRouter(<PostCard post={post} />);
    const mentionLink = screen.getByRole("link", { name: "@maria" });
    const tagLink = screen.getByRole("link", { name: "#Lumen" });
    expect(mentionLink).toHaveAttribute("href", "/profile/maria");
    expect(tagLink).toHaveAttribute("href", "/explore?hashtag=lumen");

    mockNavigate.mockClear();
    fireEvent.click(mentionLink);
    fireEvent.click(tagLink);
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("5. Normaliza Unicode NFD, ignora ftp:// e renderiza #hashtag em CommentItem", () => {
    renderWithRouter(
      <p>
        <RichText text={"Veja #cafe\u0301 ftp://host.org/#sec e foo@bar"} />
      </p>
    );

    expect(screen.getByRole("link", { name: "#café" })).toHaveAttribute(
      "href",
      "/explore?hashtag=caf%C3%A9"
    );
    expect(screen.queryByRole("link", { name: "#sec" })).toBeNull();
    expect(screen.queryByRole("link", { name: "@bar" })).toBeNull();

    const comment = {
      id: "c-tag-1",
      content_text: "Concordo com @ana sobre #Arte",
      author: { username: "pedro", avatar: null },
      created_at: new Date().toISOString(),
      likes_count: 0,
      replies_count: 0,
      preview_replies: [],
    };
    renderWithRouter(<CommentItem comment={comment} postId="p-1" />);
    expect(screen.getByRole("link", { name: "@ana" })).toHaveAttribute("href", "/profile/ana");
    expect(screen.getByRole("link", { name: "#Arte" })).toHaveAttribute(
      "href",
      "/explore?hashtag=arte"
    );
  });

  it("6. Ignora fragmentos/menções após parênteses em URLs estilo Wikipedia", () => {
    renderWithRouter(
      <p>
        <RichText text="Veja https://en.wikipedia.org/wiki/Python_(programming_language)#History e #Python" />
      </p>
    );

    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveTextContent("#Python");
    expect(links[0]).toHaveAttribute("href", "/explore?hashtag=python");
    expect(screen.queryByRole("link", { name: "#History" })).toBeNull();
  });

  it("7. Ignora menções com prefixo Unicode e hashtags que expandem além de 50 chars em lowercase", () => {
    const overflowTag = "#" + "İ".repeat(40);
    renderWithRouter(
      <p>
        <RichText text={`olá@alice ${overflowTag} @bob99`} />
      </p>
    );

    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveTextContent("@bob99");
    expect(links[0]).toHaveAttribute("href", "/profile/bob99");
  });
});
