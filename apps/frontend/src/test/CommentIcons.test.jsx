import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  HeartIcon,
  SpeechBubbleIcon,
  BookmarkIcon,
  SocialActionIcon,
  SparkleIcon,
  CloudBubbleIcon,
} from "../components/CommentIcons";

describe("CommentIcons Component", () => {
  it("renderiza HeartIcon em modos normal e preenchido", () => {
    const { rerender } = render(<HeartIcon filled={false} />);
    expect(screen.getByTestId("heart-icon")).toBeInTheDocument();

    rerender(<HeartIcon filled={true} />);
    expect(screen.getByTestId("heart-icon")).toBeInTheDocument();
  });

  it("renderiza SpeechBubbleIcon em modos normal e preenchido", () => {
    const { rerender } = render(<SpeechBubbleIcon filled={false} />);
    expect(screen.getByTestId("speech-bubble-icon")).toBeInTheDocument();

    rerender(<SpeechBubbleIcon filled={true} />);
    expect(screen.getByTestId("speech-bubble-icon")).toBeInTheDocument();
  });

  it("renderiza BookmarkIcon em modos normal e preenchido", () => {
    const { rerender } = render(<BookmarkIcon filled={false} />);
    expect(screen.getByTestId("bookmark-icon")).toBeInTheDocument();

    rerender(<BookmarkIcon filled={true} />);
    expect(screen.getByTestId("bookmark-icon")).toBeInTheDocument();
  });

  it("SocialActionIcon despacha corretamente para cada tipo", () => {
    const { rerender } = render(<SocialActionIcon type="heart" active={true} />);
    expect(screen.getByTestId("heart-icon")).toBeInTheDocument();

    rerender(<SocialActionIcon type="like" active={false} />);
    expect(screen.getByTestId("heart-icon")).toBeInTheDocument();

    rerender(<SocialActionIcon type="comment" active={true} />);
    expect(screen.getByTestId("speech-bubble-icon")).toBeInTheDocument();

    rerender(<SocialActionIcon type="reply" active={false} />);
    expect(screen.getByTestId("speech-bubble-icon")).toBeInTheDocument();

    rerender(<SocialActionIcon type="bookmark" active={true} />);
    expect(screen.getByTestId("bookmark-icon")).toBeInTheDocument();

    rerender(<SocialActionIcon type="save" active={false} />);
    expect(screen.getByTestId("bookmark-icon")).toBeInTheDocument();

    rerender(<SocialActionIcon type="unknown" />);
    expect(screen.queryByTestId("heart-icon")).not.toBeInTheDocument();
  });

  it("Aliases SparkleIcon e CloudBubbleIcon funcionam", () => {
    render(<SparkleIcon />);
    expect(screen.getByTestId("heart-icon")).toBeInTheDocument();

    render(<CloudBubbleIcon />);
    expect(screen.getByTestId("speech-bubble-icon")).toBeInTheDocument();
  });

  it("ThinkingBubbleIcon renderiza corretamente", async () => {
    const { default: ThinkingBubbleIcon } = await import("../components/ThinkingBubbleIcon");
    render(<ThinkingBubbleIcon size={22} />);
    expect(screen.getByTestId("thinking-bubble-icon")).toBeInTheDocument();
  });
});
