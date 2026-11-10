export function ThinkingBubbleIcon({ className = "", size = 18, style = {} }) {
  return (
    <div
      style={{
        maskImage: "url('/icons8-thinking-bubble-50.png')",
        WebkitMaskImage: "url('/icons8-thinking-bubble-50.png')",
        maskSize: "contain",
        WebkitMaskSize: "contain",
        maskRepeat: "no-repeat",
        WebkitMaskRepeat: "no-repeat",
        maskPosition: "center",
        WebkitMaskPosition: "center",
        backgroundColor: "currentColor",
        transform: "scaleX(-1)",
        width: `${size}px`,
        height: `${size}px`,
        display: "block",
        flexShrink: 0,
        ...style,
      }}
      className={className}
      data-testid="thinking-bubble-icon"
      aria-hidden="true"
    />
  );
}

export default ThinkingBubbleIcon;
