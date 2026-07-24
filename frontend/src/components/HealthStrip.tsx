import { useQuery } from '@tanstack/react-query'
import { getHealth } from '../api/endpoints'
import { POLL_SLOW, qk } from '../lib/queryKeys'
import { Badge } from './ui/Badge'

const SUCCESS = 'var(--color-success)'
const WARNING = 'var(--color-warning)'
const ERROR = 'var(--color-error)'
const DIM = 'var(--color-dim)'

export function HealthStrip() {
  const { data: health } = useQuery({
    queryKey: qk.health,
    queryFn: getHealth,
    refetchInterval: POLL_SLOW,
  })

  if (!health) return <Badge dot color={DIM}>checking…</Badge>

  const chips: { label: string; color: string }[] = []
  if (health.share_ok) {
    chips.push({ label: 'share ok', color: SUCCESS })
    if (health.disk_free_gb != null) {
      const free = health.disk_free_gb
      chips.push({
        label: `${free.toFixed(0)} GB free`,
        color: free > 50 ? SUCCESS : free > 10 ? WARNING : ERROR,
      })
    }
    if (health.db_size_mb != null) {
      chips.push({ label: `db ${health.db_size_mb.toFixed(1)} MB`, color: DIM })
    }
  } else {
    chips.push({ label: 'share unreachable', color: ERROR })
  }

  const vram =
    health.vram_used_gb != null && health.vram_total_gb != null
      ? `${health.vram_used_gb.toFixed(1)}/${health.vram_total_gb.toFixed(0)} GB`
      : ''
  if (health.model_loaded) {
    chips.push({ label: `model loaded${vram ? ' ' + vram : ''}`, color: WARNING })
  } else if (vram) {
    chips.push({ label: `vram ${vram}`, color: DIM })
  } else {
    chips.push({ label: 'gpu idle', color: DIM })
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {chips.map((c) => (
        <Badge key={c.label} dot glow color={c.color}>
          {c.label}
        </Badge>
      ))}
    </div>
  )
}
