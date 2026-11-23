import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { UserMiniCard } from "../components/UserMiniCard";
import { AuthContext } from "../hooks/useAuth";

function renderWithAuth(user = null) {
  return render(
    <AuthContext.Provider value={{ user, loading: false }}>
      <MemoryRouter>
        <UserMiniCard />
      </MemoryRouter>
    </AuthContext.Provider>
  );
}

describe("UserMiniCard Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. Retorna null quando não há usuário autenticado", () => {
    const { container } = renderWithAuth(null);
    expect(container).toBeEmptyDOMElement();
  });

  it("2. Renderiza dados do usuário com avatar e display_name", () => {
    renderWithAuth({
      username: "yasuo",
      display_name: "Yasuo Blossom",
      avatar: "https://example.com/avatar.png",
    });

    expect(screen.getByText("Yasuo Blossom")).toBeInTheDocument();
    expect(screen.getByText("@yasuo")).toBeInTheDocument();
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", "https://example.com/avatar.png");
    expect(img).toHaveAttribute("alt", "Yasuo Blossom");
  });

  it("3. Renderiza inicial quando usuário não possui avatar nem display_name", () => {
    renderWithAuth({
      username: "ahri",
    });

    expect(screen.getByText("ahri")).toBeInTheDocument();
    expect(screen.getByText("@ahri")).toBeInTheDocument();
    expect(screen.getByText("A")).toBeInTheDocument();
  });

  it("4. Renderiza fallback 'Você' quando user é objeto vazio", () => {
    renderWithAuth({});
    expect(screen.getByText("Você")).toBeInTheDocument();
  });
});
