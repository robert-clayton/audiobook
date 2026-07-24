/** Flat opacity-pulse placeholder block (no gradient shimmer — off-brand). */
export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div
      className={`rounded-sm ${className}`}
      style={{ animation: 'skeleton-pulse 1.6s ease-in-out infinite' }}
    />
  )
}
