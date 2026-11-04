import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { FollowButton } from "../components/FollowButton";
import { api } from "../services/api";
import "../i18n";

describe("FollowButton Component (2 testes)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. Renderiza 'Seguir' inicialmente e chama POST ao clicar, alternando para 'Deixar de seguir'", async () => {
    vi.spyOn(api, "post").mockResolvedValueOnce({ data: { detail: "Seguindo com sucesso." } });

    render(<FollowButton username="lucas" isFollowing={false} />);

    const button = screen.getByTestId("follow-button");
    expect(button).toHaveTextContent("Seguir");

    fireEvent.click(button);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/social/follow/lucas/");
      expect(button).toHaveTextContent("Deixar de seguir");
    });
  });

  it("2. Renderiza 'Deixar de seguir' e chama DELETE ao clicar, alternando para 'Seguir'", async () => {
    vi.spyOn(api, "delete").mockResolvedValueOnce({ status: 204 });

    render(<FollowButton username="lucas" isFollowing={true} />);

    const button = screen.getByTestId("follow-button");
    expect(button).toHaveTextContent("Deixar de seguir");

    fireEvent.click(button);

    await waitFor(() => {
      expect(api.delete).toHaveBeenCalledWith("/api/social/follow/lucas/");
      expect(button).toHaveTextContent("Seguir");
    });
  });
});
