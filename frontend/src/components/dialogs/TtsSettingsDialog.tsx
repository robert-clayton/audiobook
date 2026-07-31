import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { ApiError } from '../../api/client'
import { getConfig, putTtsSettings } from '../../api/endpoints'
import { qk } from '../../lib/queryKeys'
import { Button } from '../ui/Button'
import { Modal } from '../ui/Modal'
import { NumberInput } from '../ui/NumberInput'
import { Switch } from '../ui/Switch'

interface Props {
  open: boolean
  onClose: () => void
}

const DEFAULT_BATCH = 5

export function TtsSettingsDialog({ open, onClose }: Props) {
  const queryClient = useQueryClient()
  const [batchSize, setBatchSize] = useState<number | null>(DEFAULT_BATCH)
  const [verbose, setVerbose] = useState(false)
  const [saving, setSaving] = useState(false)

  const { data: config } = useQuery({
    queryKey: qk.config,
    queryFn: getConfig,
    enabled: open,
    staleTime: 0,
  })

  useEffect(() => {
    if (!open || !config) return
    setBatchSize((config.config.tts_batch_size as number | undefined) ?? DEFAULT_BATCH)
    setVerbose(Boolean(config.config.tts_verbose))
  }, [open, config])

  const save = async () => {
    const size = batchSize ?? DEFAULT_BATCH
    if (size < 1 || size > 32) {
      toast.warning('Batch size must be between 1 and 32')
      return
    }
    setSaving(true)
    try {
      await putTtsSettings({ tts_batch_size: size, tts_verbose: verbose })
      void queryClient.invalidateQueries({ queryKey: qk.config })
      toast.success('TTS settings saved — applies from the next job')
      onClose()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not save settings')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="TTS Settings"
      maxWidth="max-w-md"
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
      <div className="flex w-full flex-col gap-4">
        <div className="flex w-full flex-col gap-1.5">
          <NumberInput
            label="Batch size (chunks per generate call)"
            value={batchSize}
            min={1}
            max={32}
            step={1}
            onChange={setBatchSize}
            className="w-28"
          />
          <p className="text-[11px] leading-relaxed text-dim">
            VRAM-bound. 8 is benchmarked-safe with the GPU otherwise free; drop to
            4–5 when games or other GPU apps will be running, 1–2 if VRAM is very
            tight. Higher = faster generation until VRAM spills to system RAM,
            which silently craters speed.
          </p>
        </div>
        <div className="flex w-full flex-col gap-1.5">
          <Switch label="Verbose phase timing" checked={verbose} onChange={setVerbose} />
          <p className="text-[11px] leading-relaxed text-dim">
            Logs [t] lines per chapter: generation RT per batch, merge/mp3/share
            timings. Costs nothing measurable.
          </p>
        </div>
        <p className="border-t border-border pt-3 text-[11px] text-dim">
          Settings are read at job start — a queued or running job keeps the
          values it launched with.
        </p>
      </div>
    </Modal>
  )
}
