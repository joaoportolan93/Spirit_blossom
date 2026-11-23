/**
 * SkeletonCard — Shimmer de carregamento que imita a geometria de um PostCard.
 * Usado enquanto o feed ainda não tem dados.
 */
export function SkeletonCard() {
  return (
    <div
      aria-hidden="true"
      className="bg-zinc-900 border border-zinc-800/60 rounded-2xl p-4 shadow-sm animate-pulse"
    >
      {/* Header */}
      <div className="flex items-center gap-3 mb-3">
        <div className="w-10 h-10 rounded-full bg-zinc-800 shrink-0" />
        <div className="flex-1 space-y-2">
          <div className="h-3 bg-zinc-800 rounded-full w-28" />
          <div className="h-2.5 bg-zinc-800/70 rounded-full w-20" />
        </div>
      </div>
      {/* Body */}
      <div className="space-y-2 mb-4">
        <div className="h-3 bg-zinc-800 rounded-full w-full" />
        <div className="h-3 bg-zinc-800 rounded-full w-5/6" />
        <div className="h-3 bg-zinc-800/50 rounded-full w-3/4" />
      </div>
      {/* Footer */}
      <div className="flex gap-6 pt-2 border-t border-zinc-800/50">
        <div className="h-3 bg-zinc-800 rounded-full w-10" />
        <div className="h-3 bg-zinc-800 rounded-full w-10" />
        <div className="h-3 bg-zinc-800 rounded-full w-10" />
      </div>
    </div>
  );
}

export function SkeletonList({ count = 3 }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}
