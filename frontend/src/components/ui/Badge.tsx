import type { ReactNode } from 'react'

interface Props {
  color?: string // CSS color for border/text/dot; defaults to dim
  dot?: boolean
  glow?: boolean // terminal-LED glow on the dot
  children: ReactNode
  title?: string
}

/** Bordered chip: health indicators, DEV tag, transcript status, etc. */
export function Badge({ color = 'var(--color-dim)', dot, glow, children, title }: Props) {
  return (
    <span
      title={title}
      className="inline-flex items-center gap-1.5 rounded-sm border px-2 py-px text-[11px]
        whitespace-nowrap"
      style={{ borderColor: color, color }}
    >
      {dot && (
        <span
          className="inline-block h-1.5 w-1.5 rounded-full"
          style={{ background: color, boxShadow: glow ? `0 0 5px ${color}` : undefined }}
        />
      )}
      {children}
    </span>
  )
}
