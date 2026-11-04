import { formatDistanceToNow } from "../utils/date";

export function PostCard({ post }) {
  const authorName = post.author?.username || "anônimo";
  const dateFormatted = post.created_at ? formatDistanceToNow(post.created_at) : "";

  return (
    <article
      data-testid="post-card"
      className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 mb-4 hover:border-zinc-700 transition"
    >
      <header className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center font-bold text-xs text-zinc-300">
            {authorName[0]?.toUpperCase()}
          </div>
          <span className="font-semibold text-sm text-zinc-200">@{authorName}</span>
        </div>
        {dateFormatted && (
          <time className="text-xs text-zinc-500">{dateFormatted}</time>
        )}
      </header>

      {/* RENDERIZADO ESTRITAMENTE COMO TEXTO PURO (SEM RISCO DE XSS) */}
      <p
        data-testid="post-content"
        className="text-sm text-zinc-100 whitespace-pre-wrap break-words"
      >
        {post.content_text}
      </p>
    </article>
  );
}
