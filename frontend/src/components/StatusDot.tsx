/** Chapter-status LED: colored dot, glow, pulse while processing. */

const STATUS_COLORS: Record<string, string> = {
  done: 'var(--color-success)',
  pending: 'var(--color-info)',
  failed: 'var(--color-error)',
  processing: 'var(--color-accent)',
}

export function statusColor(status: string): string {
  return STATUS_COLORS[status] ?? 'var(--color-dim)'
}

export function StatusDot({ status, size = 8 }: { status: string; size?: number }) {
  const color = statusColor(status)
  return (
    <span
      className="inline-block shrink-0 rounded-full"
      style={{
        width: size,
        height: size,
        background: color,
        boxShadow: `0 0 5px ${color}`,
        animation: status === 'processing' ? 'pulse-dot 2s ease-in-out infinite' : undefined,
      }}
    />
  )
}
