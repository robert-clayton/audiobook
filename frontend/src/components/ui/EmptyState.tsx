import type { ReactNode } from 'react'

/** Centered dim terminal-style empty message: `[ no failed chapters ]` */
export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center justify-center py-10 text-[13px] text-dim select-none">
      <span className="opacity-60">[&nbsp;</span>
      {children}
      <span className="opacity-60">&nbsp;]</span>
    </div>
  )
}
