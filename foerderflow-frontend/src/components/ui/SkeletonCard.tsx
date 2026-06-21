export function SkeletonCard() {
  return (
    <div
      className="rounded-soft-sm border border-soft-line bg-soft-surface p-5 animate-pulse"
      aria-hidden="true"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="h-5 w-48 bg-soft-line rounded" />
        <div className="flex gap-2">
          <div className="h-5 w-12 bg-soft-line rounded-full" />
          <div className="h-5 w-16 bg-soft-line rounded-full" />
        </div>
      </div>
      <div className="h-4 w-32 bg-soft-line2 rounded mb-2" />
      <div className="h-4 w-24 bg-soft-line2 rounded" />
    </div>
  );
}

export function SkeletonList({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3" role="status" aria-label="Wird geladen…">
      <span className="sr-only">Wird geladen…</span>
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}
