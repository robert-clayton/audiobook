import { AlertTriangle } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { ApiError } from '../../api/client'
import { rescrapeSeriesApply } from '../../api/endpoints'
import type { SeriesRescrapePreview } from '../../api/types'
import { unifiedDiff } from '../../lib/diff'
import { DiffStats, DiffView } from '../DiffView'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Checkbox } from '../ui/Checkbox'
import { Collapsible } from '../ui/Collapsible'
import { Modal } from '../ui/Modal'

interface Props {
  series: string
  preview: SeriesRescrapePreview | null
  onClose: () => void
  onApplied?: (count: number) => void
}

/** Whole-series rescrape review: per-chapter diffs with checkboxes. */
export function RescrapeSeriesDialog({ series, preview, onClose, onApplied }: Props) {
  const changes = preview?.changes ?? []
  const unavailable = preview?.unavailable ?? []

  const [selected, setSelected] = useState<Set<number>>(
    () => new Set(changes.map((c) => c.chapter_id)),
  )
  const [applying, setApplying] = useState(false)

  const diffs = useMemo(
    () => changes.map((c) => unifiedDiff(c.old_text, c.new_text)),
    [changes],
  )

  if (!preview) return null

  const toggle = (id: number, on: boolean) => {
    const next = new Set(selected)
    if (on) next.add(id)
    else next.delete(id)
    setSelected(next)
  }

  const allSelected = selected.size === changes.length && changes.length > 0

  const summaryParts: string[] = []
  if (changes.length) summaryParts.push(`${changes.length} changed`)
  if (unavailable.length) summaryParts.push(`${unavailable.length} deleted/drafted`)

  const apply = async () => {
    const toApply = changes.filter((c) => selected.has(c.chapter_id))
    if (!toApply.length) {
      toast.warning('No chapters selected')
      return
    }
    setApplying(true)
    try {
      const res = await rescrapeSeriesApply(
        series,
        toApply.map((c) => ({ chapter_id: c.chapter_id, new_text: c.new_text })),
      )
      toast.success(`Updated ${res.applied} chapter(s)`)
      onApplied?.(res.applied)
      onClose()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not apply rescrapes')
    } finally {
      setApplying(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Rescrape: ${series}`}
      maxWidth="max-w-5xl"
      tall
      headerExtra={<span className="text-[12px] text-dim">{summaryParts.join(', ')}</span>}
      footer={
        <>
          {changes.length > 0 && (
            <span className="mr-auto">
              <Checkbox
                checked={allSelected}
                indeterminate={!allSelected && selected.size > 0}
                onChange={(on) =>
                  setSelected(on ? new Set(changes.map((c) => c.chapter_id)) : new Set())
                }
                label={`select all (${selected.size}/${changes.length})`}
              />
            </span>
          )}
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          {changes.length > 0 && (
            <Button variant="accent" disabled={applying} onClick={() => void apply()}>
              {applying ? 'Applying…' : `Apply Selected (${selected.size})`}
            </Button>
          )}
        </>
      }
    >
      <div className="flex w-full flex-col gap-1">
        {unavailable.map((u) => (
          <div key={u.chapter_id} className="flex w-full items-center gap-2 px-1 py-1">
            <AlertTriangle size={14} className="shrink-0 text-accent" />
            <span className="min-w-0 flex-grow truncate text-[13px]">{u.title}</span>
            <Badge color="var(--color-accent)">deleted / drafted</Badge>
          </div>
        ))}
        {changes.map((change, i) => (
          <div key={change.chapter_id} className="flex w-full items-start gap-2">
            <span className="pt-1.5">
              <Checkbox
                checked={selected.has(change.chapter_id)}
                onChange={(on) => toggle(change.chapter_id, on)}
              />
            </span>
            <Collapsible
              summary={
                <span className="inline-flex items-center gap-2">
                  {change.title}
                  <DiffStats added={diffs[i].added} removed={diffs[i].removed} />
                </span>
              }
            >
              <DiffView lines={diffs[i].lines} />
            </Collapsible>
          </div>
        ))}
      </div>
    </Modal>
  )
}
