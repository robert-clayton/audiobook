import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { ApiError } from '../../api/client'
import { getTranscript, putTranscript } from '../../api/endpoints'
import { qk } from '../../lib/queryKeys'
import { Button } from '../ui/Button'
import { Modal } from '../ui/Modal'
import { Textarea } from '../ui/Textarea'

interface Props {
  speaker: string | null
  onClose: () => void
}

export function TranscriptDialog({ speaker, onClose }: Props) {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState('')
  const [saving, setSaving] = useState(false)

  const open = speaker !== null
  const { data } = useQuery({
    queryKey: ['transcript', speaker],
    queryFn: () => getTranscript(speaker!),
    enabled: open,
    staleTime: 0,
  })

  useEffect(() => {
    if (open && data) setDraft(data.text)
  }, [open, data])

  if (!speaker) return null
  const dirty = data !== undefined && draft !== data.text

  const save = async () => {
    if (!draft.trim()) {
      toast.warning('Transcript is empty — not saved')
      return
    }
    setSaving(true)
    try {
      await putTranscript(speaker, draft)
      void queryClient.invalidateQueries({ queryKey: qk.speakers })
      toast.success(`Transcript saved for ${speaker}`)
      onClose()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not save transcript')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Transcript: ${speaker}`}
      onBeforeClose={() => !dirty || window.confirm('Discard unsaved transcript changes?')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="accent" disabled={saving} onClick={() => void save()}>
            {saving ? 'Saving…' : 'Save'}
          </Button>
        </>
      }
    >
      <div className="flex w-full flex-col gap-3">
        {data !== undefined && !data.text && (
          <p className="text-[12px] text-warning">
            No transcript yet — adding one significantly improves voice cloning quality.
          </p>
        )}
        <Textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={8}
          placeholder="Exact transcript of the reference audio…"
        />
        <p className="text-[11px] text-dim">
          Note: an already-loaded TTS model keeps its cached voice prompt until the job
          queue drains and the model unloads.
        </p>
      </div>
    </Modal>
  )
}
