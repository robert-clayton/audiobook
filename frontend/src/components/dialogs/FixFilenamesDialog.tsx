import { MoveRight } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { ApiError } from '../../api/client'
import { applyFilenameFixes } from '../../api/endpoints'
import type { FilenameFix } from '../../api/types'
import { Button } from '../ui/Button'
import { Checkbox } from '../ui/Checkbox'
import { Modal } from '../ui/Modal'

interface Props {
  series: string
  fixes: FilenameFix[] | null
  onClose: () => void
  onApplied?: (count: number) => void
}

/** Filename mismatch review: old title (strikethrough) → new title. */
export function FixFilenamesDialog({ series, fixes, onClose, onApplied }: Props) {
  const [selected, setSelected] = useState<Set<number>>(
    () => new Set((fixes ?? []).map((f) => f.chapter_id)),
  )
  const [applying, setApplying] = useState(false)

  if (!fixes) return null

  const toggle = (id: number, on: boolean) => {
    const next = new Set(selected)
    if (on) next.add(id)
    else next.delete(id)
    setSelected(next)
  }
  const allSelected = selected.size === fixes.length && fixes.length > 0

  const apply = async () => {
    if (!selected.size) {
      toast.warning('No files selected')
      return
    }
    setApplying(true)
    try {
      const res = await applyFilenameFixes(series, [...selected])
      toast.success(`Renamed ${res.renamed} file(s)`)
      onApplied?.(res.renamed)
      onClose()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not rename files')
    } finally {
      setApplying(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Fix Filenames: ${series}`}
      maxWidth="max-w-4xl"
      headerExtra={<span className="text-[12px] text-dim">{fixes.length} file(s) to rename</span>}
      footer={
        <>
          <span className="mr-auto">
            <Checkbox
              checked={allSelected}
              indeterminate={!allSelected && selected.size > 0}
              onChange={(on) =>
                setSelected(on ? new Set(fixes.map((f) => f.chapter_id)) : new Set())
              }
              label={`select all (${selected.size}/${fixes.length})`}
            />
          </span>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="accent" disabled={applying} onClick={() => void apply()}>
            {applying ? 'Renaming…' : 'Apply'}
          </Button>
        </>
      }
    >
      <div className="flex w-full flex-col gap-1">
        {fixes.map((fix) => (
          <div key={fix.chapter_id} className="flex w-full items-center gap-2 px-1 py-0.5 text-[13px]">
            <Checkbox
              checked={selected.has(fix.chapter_id)}
              onChange={(on) => toggle(fix.chapter_id, on)}
            />
            <span className="text-error line-through">{fix.old_title}</span>
            <MoveRight size={13} className="shrink-0 text-dim" />
            <span className="text-success">{fix.new_title}</span>
          </div>
        ))}
      </div>
    </Modal>
  )
}
