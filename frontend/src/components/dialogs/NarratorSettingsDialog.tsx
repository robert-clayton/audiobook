import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { ApiError } from '../../api/client'
import { getConfig, getConfigMeta, putNarrators } from '../../api/endpoints'
import { qk } from '../../lib/queryKeys'
import { Button } from '../ui/Button'
import { IconButton } from '../ui/IconButton'
import { Modal } from '../ui/Modal'
import { NumberInput } from '../ui/NumberInput'
import { Select } from '../ui/Select'

interface Props {
  open: boolean
  onClose: () => void
}

interface NarratorRow {
  name: string
  pause: number | null
  volume: number | null
}

export function NarratorSettingsDialog({ open, onClose }: Props) {
  const [rows, setRows] = useState<NarratorRow[]>([])
  const [addName, setAddName] = useState('')
  const [saving, setSaving] = useState(false)
  const queryClient = useQueryClient()

  const { data: config } = useQuery({
    queryKey: qk.config,
    queryFn: getConfig,
    enabled: open,
    staleTime: 0,
  })
  const { data: meta } = useQuery({
    queryKey: qk.configMeta,
    queryFn: getConfigMeta,
    staleTime: Infinity,
    enabled: open,
  })

  // Seed rows from config when the dialog opens / config loads.
  useEffect(() => {
    if (!open || !config) return
    const narrators: Record<string, { pause?: number; volume?: number }> = {
      default: {},
      ...(config.config.narrators ?? {}),
    }
    const seeded = Object.entries(narrators).map(([name, v]) => ({
      name,
      pause: v?.pause ?? null,
      volume: v?.volume ?? null,
    }))
    seeded.sort((a, b) =>
      a.name === 'default' ? -1 : b.name === 'default' ? 1 : a.name.localeCompare(b.name),
    )
    setRows(seeded)
  }, [open, config])

  const used = new Set(rows.map((r) => r.name))
  const addable = (meta?.speakers ?? []).filter((s) => !used.has(s))

  const update = (name: string, patch: Partial<NarratorRow>) =>
    setRows(rows.map((r) => (r.name === name ? { ...r, ...patch } : r)))

  const save = async () => {
    setSaving(true)
    try {
      const narrators: Record<string, { pause?: number; volume?: number }> = {}
      for (const r of rows) {
        const entry: { pause?: number; volume?: number } = {}
        if (r.pause != null) entry.pause = r.pause
        if (r.volume != null) entry.volume = r.volume
        if (Object.keys(entry).length || r.name === 'default') narrators[r.name] = entry
      }
      await putNarrators(narrators)
      void queryClient.invalidateQueries({ queryKey: qk.config })
      toast.success('Narrator settings saved')
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
      title="Narrator Settings"
      maxWidth="max-w-2xl"
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
      <div className="flex w-full flex-col gap-1.5">
        <div className="flex w-full items-center gap-2 text-[11px] tracking-wide text-dim uppercase">
          <span className="flex-grow">narrator</span>
          <span className="w-24 shrink-0">pause (s)</span>
          <span className="w-24 shrink-0">volume</span>
          <span className="w-7 shrink-0" />
        </div>
        {rows.map((row) => (
          <div key={row.name} className="flex w-full items-center gap-2">
            <span className="min-w-0 flex-grow truncate text-[13px]">{row.name}</span>
            <NumberInput
              value={row.pause}
              min={0}
              max={5}
              step={0.05}
              onChange={(v) => update(row.name, { pause: v })}
              className="w-24 shrink-0"
            />
            <NumberInput
              value={row.volume}
              min={0.1}
              max={3}
              step={0.05}
              onChange={(v) => update(row.name, { volume: v })}
              className="w-24 shrink-0"
            />
            <span className="w-7 shrink-0">
              {row.name !== 'default' && (
                <IconButton
                  title="Remove narrator"
                  danger
                  onClick={() => setRows(rows.filter((r) => r.name !== row.name))}
                >
                  <X size={14} />
                </IconButton>
              )}
            </span>
          </div>
        ))}

        <div className="mt-3 flex w-full items-center gap-2 border-t border-border pt-3">
          <Select
            options={addable}
            value={addName}
            allowEmpty
            emptyLabel="add narrator…"
            onChange={(e) => setAddName(e.target.value)}
            className="w-64"
          />
          <IconButton
            title="Add narrator"
            disabled={!addName}
            onClick={() => {
              if (!addName) return
              setRows([...rows, { name: addName, pause: null, volume: null }])
              setAddName('')
            }}
          >
            <Plus size={14} className="text-accent" />
          </IconButton>
        </div>
      </div>
    </Modal>
  )
}
