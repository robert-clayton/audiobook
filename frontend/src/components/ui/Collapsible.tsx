import { ChevronRight } from 'lucide-react'
import { useState, type ReactNode } from 'react'

interface Props {
  summary: ReactNode
  children: ReactNode
  defaultOpen?: boolean
}

export function Collapsible({ summary, children, defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="w-full">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full cursor-pointer items-center gap-1.5 rounded-sm px-1 py-1
          text-left text-[13px] text-text transition-colors duration-150 hover:bg-dim/10"
      >
        <ChevronRight
          size={14}
          className={`shrink-0 text-dim transition-transform duration-150 ${open ? 'rotate-90' : ''}`}
        />
        <span className="min-w-0 flex-grow">{summary}</span>
      </button>
      {open && <div className="pt-1 pl-5">{children}</div>}
    </div>
  )
}
