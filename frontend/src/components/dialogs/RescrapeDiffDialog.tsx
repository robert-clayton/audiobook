import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { ApiError } from '../../api/client'
import { rescrapeChapterApply } from '../../api/endpoints'
import type { Chapter, RescrapePreview } from '../../api/types'
import { unifiedDiff } from '../../lib/diff'
import { DiffStats, DiffView } from '../DiffView'
import { Button } from '../ui/Button'
import { Modal } from '../ui/Modal'

interface Props {
  chapter: Chapter | null
  preview: RescrapePreview | null
  series: string
  onClose: () => void
  onApplied?: () => void
}

/** Single-chapter rescrape review: unified diff, Keep Old / Accept New. */
export function RescrapeDiffDialog({ chapter, preview, series, onClose, onApplied }: Props) {
  const [applying, setApplying] = useState(false)

  const diff = useMemo(
    () => (preview ? unifiedDiff(preview.old_text, preview.new_text) : null),
    [preview],
  )

  if (!chapter || !preview || !diff) return null

  const accept = async () => {
    setApplying(true)
    try {
      await rescrapeChapterApply(chapter.id, series, preview.new_text)
      toast.success(`Updated: ${chapter.title}`)
      onApplied?.()
      onClose()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not apply rescrape')
    } finally {
      setApplying(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Rescrape: ${chapter.title}`}
      maxWidth="max-w-5xl"
      tall
      headerExtra={<DiffStats added={diff.added} removed={diff.removed} />}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Keep Old
          </Button>
          <Button variant="accent" disabled={applying} onClick={() => void accept()}>
            {applying ? 'Applying…' : 'Accept New'}
          </Button>
        </>
      }
    >
      <DiffView lines={diff.lines} />
    </Modal>
  )
}
