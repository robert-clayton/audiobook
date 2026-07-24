import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from 'sonner'
import { ApiError } from '../../api/client'
import { addSeries, getConfigMeta } from '../../api/endpoints'
import { qk } from '../../lib/queryKeys'
import { Button } from '../ui/Button'
import { Modal } from '../ui/Modal'
import { Select } from '../ui/Select'
import { TextInput } from '../ui/TextInput'

interface Props {
  open: boolean
  onClose: () => void
  onAdded?: (name: string) => void
}

const isLocal = (url: string) => url.trim().toLowerCase() === 'local'

export function AddSeriesDialog({ open, onClose, onAdded }: Props) {
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [latest, setLatest] = useState('')
  const [narrator, setNarrator] = useState('')
  const [saving, setSaving] = useState(false)

  const { data: meta } = useQuery({
    queryKey: qk.configMeta,
    queryFn: getConfigMeta,
    staleTime: Infinity,
    enabled: open,
  })

  const reset = () => {
    setName('')
    setUrl('')
    setLatest('')
    setNarrator('')
  }

  const save = async () => {
    // Client-side pre-checks mirror the server; the server re-validates.
    if (!name.trim()) return toast.warning('Series name is required')
    if (!narrator) return toast.warning('Pick a narrator')
    if (!isLocal(url) && !latest.trim())
      return toast.warning('First chapter URL is required for scraped series')

    setSaving(true)
    try {
      await addSeries({
        name: name.trim(),
        url: url.trim(),
        latest: latest.trim() || undefined,
        narrator,
      })
      toast.success(`Added series: ${name.trim()}`)
      onAdded?.(name.trim())
      reset()
      onClose()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not add series')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add Series"
      maxWidth="max-w-2xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="success" disabled={saving} onClick={() => void save()}>
            {saving ? 'Adding…' : 'Add'}
          </Button>
        </>
      }
    >
      <div className="flex w-full flex-col gap-3">
        <TextInput label="Series name" value={name} onChange={(e) => setName(e.target.value)} />
        <TextInput
          label="Series URL (or 'local' for manually managed chapters)"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder={meta ? `supported: ${meta.sources.join(', ')} or 'local'` : undefined}
        />
        {!isLocal(url) && (
          <TextInput
            label="First chapter URL (scrape starting point)"
            value={latest}
            onChange={(e) => setLatest(e.target.value)}
          />
        )}
        <Select
          label="Narrator"
          options={meta?.speakers ?? []}
          value={narrator}
          allowEmpty
          emptyLabel="pick a narrator…"
          onChange={(e) => setNarrator(e.target.value)}
        />
      </div>
    </Modal>
  )
}
