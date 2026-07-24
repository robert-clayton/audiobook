import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { ApiError } from '../../api/client'
import { getConfigMeta, patchSeriesConfig } from '../../api/endpoints'
import type { SeriesConfigEntry } from '../../api/types'
import { qk } from '../../lib/queryKeys'
import { dictToKv, KVEditor, kvToDict, type KVRow } from '../KVEditor'
import { Button } from '../ui/Button'
import { Kicker } from '../ui/Kicker'
import { Modal } from '../ui/Modal'
import { NumberInput } from '../ui/NumberInput'
import { Select } from '../ui/Select'
import { Switch } from '../ui/Switch'
import { TextInput } from '../ui/TextInput'

interface Props {
  open: boolean
  seriesConfig: SeriesConfigEntry | null
  onClose: () => void
  onSaved?: () => void
}

export function SeriesEditorDialog({ open, seriesConfig, onClose, onSaved }: Props) {
  const queryClient = useQueryClient()
  const [narrator, setNarrator] = useState('')
  const [enabled, setEnabled] = useState(true)
  const [latest, setLatest] = useState('')
  const [latestUnlocked, setLatestUnlocked] = useState(false)
  const [replacements, setReplacements] = useState<KVRow[]>([])
  const [mappings, setMappings] = useState<KVRow[]>([])
  const [sysVoice, setSysVoice] = useState('')
  const [sysModulate, setSysModulate] = useState(true)
  const [sysSpeed, setSysSpeed] = useState<number | null>(1.0)
  const [sysTypes, setSysTypes] = useState<Set<string>>(new Set())
  const [saving, setSaving] = useState(false)

  const { data: meta } = useQuery({
    queryKey: qk.configMeta,
    queryFn: getConfigMeta,
    staleTime: Infinity,
    enabled: open,
  })

  // Seed form state each time the dialog opens with a config entry.
  useEffect(() => {
    if (!open || !seriesConfig) return
    setNarrator(seriesConfig.narrator ?? '')
    setEnabled(seriesConfig.enabled ?? true)
    setLatest(seriesConfig.latest ?? '')
    setLatestUnlocked(false)
    setReplacements(dictToKv(seriesConfig.replacements))
    setMappings(dictToKv(seriesConfig.mappings))
    const system = seriesConfig.system ?? {}
    setSysVoice(system.voice ?? '')
    setSysModulate(system.modulate ?? true)
    setSysSpeed(system.speed ?? 1.0)
    setSysTypes(new Set(system.type ?? []))
  }, [open, seriesConfig])

  if (!seriesConfig) return null
  const name = seriesConfig.name

  const save = async () => {
    setSaving(true)
    try {
      const body: Record<string, unknown> = {
        narrator: narrator || undefined,
        enabled,
        replacements: kvToDict(replacements),
        mappings: kvToDict(mappings),
        system: {
          voice: sysVoice || null,
          modulate: sysModulate,
          speed: sysSpeed ?? 1.0,
          type: [...sysTypes],
        },
      }
      // The scrape cursor is only written when explicitly unlocked.
      if (latestUnlocked && latest.trim()) body.latest = latest.trim()
      await patchSeriesConfig(name, body)
      void queryClient.invalidateQueries({ queryKey: qk.config })
      void queryClient.invalidateQueries({ queryKey: qk.seriesDetail(name) })
      toast.success(`Saved config for ${name}`)
      onSaved?.()
      onClose()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not save config')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Edit Config: ${name}`}
      maxWidth="max-w-3xl"
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
        <div className="flex w-full flex-wrap items-end gap-3">
          <div className="min-w-48 flex-grow">
            <Select
              label="Narrator"
              options={meta?.speakers ?? []}
              value={narrator}
              allowEmpty
              onChange={(e) => setNarrator(e.target.value)}
            />
          </div>
          <div className="pb-1.5">
            <Switch label="Enabled" checked={enabled} onChange={setEnabled} />
          </div>
        </div>

        <div className="flex w-full items-end gap-2">
          <div className="min-w-0 flex-grow">
            <TextInput
              label="latest (scrape cursor)"
              value={latest}
              readOnly={!latestUnlocked}
              onChange={(e) => setLatest(e.target.value)}
            />
          </div>
          <div className="pb-1.5">
            <Switch
              label="unlock"
              checked={latestUnlocked}
              onChange={(on) => {
                setLatestUnlocked(on)
                if (on) toast.warning('Careful — the scraper resumes from this URL')
              }}
            />
          </div>
        </div>

        <hr className="border-border" />
        <KVEditor
          title="Replacements (word → pronunciation)"
          rows={replacements}
          onChange={setReplacements}
          keyPlaceholder="word"
          valuePlaceholder="pronunciation"
        />

        <hr className="border-border" />
        <KVEditor
          title="Mappings (character → speaker)"
          rows={mappings}
          onChange={setMappings}
          valueOptions={meta?.speakers}
          keyPlaceholder="character"
        />

        <hr className="border-border" />
        <div className="flex w-full flex-col gap-3">
          <Kicker>system voice</Kicker>
          <div className="flex w-full flex-wrap items-end gap-3">
            <div className="w-48">
              <Select
                label="Voice"
                options={meta?.speakers ?? []}
                value={sysVoice}
                allowEmpty
                onChange={(e) => setSysVoice(e.target.value)}
              />
            </div>
            <div className="pb-1.5">
              <Switch label="Modulate" checked={sysModulate} onChange={setSysModulate} />
            </div>
            <div className="w-28">
              <NumberInput
                label="Speed"
                value={sysSpeed}
                min={0.5}
                max={2}
                step={0.05}
                onChange={setSysSpeed}
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {(meta?.system_types ?? []).map((t) => {
              const on = sysTypes.has(t)
              return (
                <button
                  key={t}
                  type="button"
                  onClick={() => {
                    const next = new Set(sysTypes)
                    if (on) next.delete(t)
                    else next.add(t)
                    setSysTypes(next)
                  }}
                  className={`cursor-pointer rounded-sm border px-2.5 py-1 text-[11px]
                    tracking-wide uppercase transition-colors duration-150
                    ${
                      on
                        ? 'border-accent bg-accent/15 text-accent'
                        : 'border-border-strong text-dim hover:border-dim hover:text-text'
                    }`}
                >
                  {t}
                </button>
              )
            })}
          </div>
        </div>
      </div>
    </Modal>
  )
}
