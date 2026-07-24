/** Pipeline state badge (Idle / Scraping / Generating / Finished / Error). */

const STATE_COLORS: Record<string, string> = {
  Idle: 'var(--color-dim)',
  Scraping: 'var(--color-info)',
  Generating: 'var(--color-accent)',
  Finished: 'var(--color-success)',
  Error: 'var(--color-error)',
  Cancelled: 'var(--color-warning)',
}

export function StatusBadge({ state, error }: { state: string; error?: string }) {
  const color = STATE_COLORS[state] ?? 'var(--color-dim)'
  const active = state === 'Scraping' || state === 'Generating'
  let label = state.toLowerCase()
  if (state === 'Error' && error) label = `error: ${error.slice(0, 60)}`
  return (
    <span className="inline-flex items-center gap-2 text-[12px]" style={{ color }} title={error}>
      <span
        className="inline-block h-2 w-2 rounded-full"
        style={{
          background: color,
          boxShadow: `0 0 6px ${color}`,
          animation: active ? 'pulse-dot 2s ease-in-out infinite' : undefined,
        }}
      />
      {label}
    </span>
  )
}
