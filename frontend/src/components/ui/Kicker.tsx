import type { ReactNode } from 'react'

/** Section label in the industrial style: `// SERIES` */
export function Kicker({ children }: { children: ReactNode }) {
  return (
    <span className="text-[11px] tracking-[0.1em] text-dim uppercase select-none">
      {'// '}
      {children}
    </span>
  )
}
