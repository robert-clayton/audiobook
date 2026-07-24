import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { ApiError } from '../../api/client'
import { getChapterText, putChapterText } from '../../api/endpoints'
import type { Chapter } from '../../api/types'
import { qk } from '../../lib/queryKeys'
import { AudioPlayer } from '../AudioPlayer'
import { Button } from '../ui/Button'
import { Modal } from '../ui/Modal'
import { Skeleton } from '../ui/Skeleton'
import { Tabs } from '../ui/Tabs'
import { Textarea } from '../ui/Textarea'

interface Props {
  chapter: Chapter | null
  series: string
  onClose: () => void
  onSaved?: () => void
}

/** Chapter viewer/editor: audio player, raw text with edit mode, cleaned preview. */
export function ChapterDialog({ chapter, series, onClose, onSaved }: Props) {
  const [tab, setTab] = useState('Raw')
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [saving, setSaving] = useState(false)

  const open = chapter !== null
  const { data, isLoading, error } = useQuery({
    queryKey: chapter ? qk.chapterText(chapter.id) : ['chapterText', 'none'],
    queryFn: () => getChapterText(chapter!.id, series),
    enabled: open,
    staleTime: 0,
  })

  // Reset view state whenever a different chapter opens.
  useEffect(() => {
    if (open) {
      setTab('Raw')
      setEditing(false)
      setDraft('')
    }
  }, [open, chapter?.id])

  if (!chapter) return null

  const dirty = editing && data !== undefined && draft !== data.text

  const save = async (regenerate: boolean) => {
    setSaving(true)
    try {
      await putChapterText(chapter.id, { series, text: draft, regenerate })
      toast.success(
        regenerate
          ? `Saved — ${chapter.title} queued for regeneration`
          : `Saved — ${chapter.title} reset to pending`,
      )
      onSaved?.()
      onClose()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not save text')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={chapter.title}
      maxWidth="max-w-4xl"
      tall
      onBeforeClose={() =>
        !dirty || window.confirm('Discard unsaved text changes?')
      }
    >
      <div className="flex min-h-0 w-full flex-grow flex-col gap-3">
        {chapter.status === 'done' && (
          <AudioPlayer src={`/api/audio/${chapter.id}`} className="w-full shrink-0" />
        )}
        <Tabs tabs={['Raw', 'Cleaned preview']} active={tab} onChange={setTab} />

        {isLoading && (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        )}
        {error !== null && (
          <p className="text-[13px] text-error">
            {error instanceof ApiError ? error.message : 'Could not load chapter text'}
          </p>
        )}

        {data && tab === 'Raw' && !editing && (
          <>
            <TextBlock text={data.text} />
            <div className="flex w-full shrink-0 justify-start">
              <Button
                variant="accent"
                onClick={() => {
                  setDraft(data.text)
                  setEditing(true)
                }}
              >
                Edit
              </Button>
            </div>
          </>
        )}

        {data && tab === 'Raw' && editing && (
          <>
            <Textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              className="min-h-0 flex-grow"
            />
            <div className="flex w-full shrink-0 justify-end gap-2">
              <Button variant="ghost" onClick={() => setEditing(false)}>
                Cancel
              </Button>
              <Button variant="accent" disabled={saving} onClick={() => void save(false)}>
                Save &amp; Reset
              </Button>
              <Button variant="success" disabled={saving} onClick={() => void save(true)}>
                Save &amp; Regenerate
              </Button>
            </div>
          </>
        )}

        {data && tab === 'Cleaned preview' && <TextBlock text={data.cleaned} />}
      </div>
    </Modal>
  )
}

function TextBlock({ text }: { text: string }) {
  return (
    <pre
      className="min-h-0 flex-grow overflow-y-auto rounded-sm border border-border bg-bg
        p-3 text-[13px] leading-relaxed whitespace-pre-wrap text-dim"
    >
      {text}
    </pre>
  )
}
