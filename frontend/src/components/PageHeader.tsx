import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useStatus } from '../hooks/useStatusPoll'
import { Badge } from './ui/Badge'
import { StatusBadge } from './StatusBadge'

interface Props {
  title: string
  titleColor?: string
  backTo?: string
  /** Dim nav links (dashboard only). */
  nav?: { label: string; to: string }[]
  extra?: ReactNode
}

export function PageHeader({ title, titleColor = 'var(--color-accent)', backTo, nav, extra }: Props) {
  const status = useStatus()
  return (
    <header className="flex w-full flex-wrap items-center gap-3">
      {backTo && (
        <Link
          to={backTo}
          className="rounded-sm p-1 text-dim transition-colors duration-150 hover:bg-dim/10 hover:text-text"
          title="Back"
        >
          <ArrowLeft size={18} />
        </Link>
      )}
      <h1 className="text-xl font-bold" style={{ color: titleColor }}>
        {title}
      </h1>
      {nav?.map((n) => (
        <Link
          key={n.to}
          to={n.to}
          className="text-xs tracking-[0.06em] text-dim transition-colors duration-150 hover:text-accent"
        >
          {n.label}
        </Link>
      ))}
      <span className="ml-auto flex items-center gap-3">
        {extra}
        <StatusBadge state={status?.state ?? 'Idle'} error={status?.error} />
        {status?.dev_mode && <Badge color="var(--color-accent)">DEV</Badge>}
      </span>
    </header>
  )
}
