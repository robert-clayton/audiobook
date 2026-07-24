import { Plus, X } from 'lucide-react'
import { Kicker } from './ui/Kicker'
import { IconButton } from './ui/IconButton'
import { Select } from './ui/Select'
import { TextInput } from './ui/TextInput'

export interface KVRow {
  k: string
  v: string
}

interface Props {
  title: string
  rows: KVRow[]
  onChange: (rows: KVRow[]) => void
  /** When given, values use a dropdown (e.g. speaker names). */
  valueOptions?: string[]
  keyPlaceholder?: string
  valuePlaceholder?: string
}

/** Editable key→value list (replacements, character→speaker mappings). */
export function KVEditor({
  title,
  rows,
  onChange,
  valueOptions,
  keyPlaceholder = 'name',
  valuePlaceholder = 'value',
}: Props) {
  const update = (index: number, patch: Partial<KVRow>) => {
    onChange(rows.map((r, i) => (i === index ? { ...r, ...patch } : r)))
  }

  return (
    <div className="flex w-full flex-col gap-1.5">
      <div className="flex w-full items-center justify-between">
        <Kicker>{title}</Kicker>
        <IconButton title="Add row" onClick={() => onChange([...rows, { k: '', v: '' }])}>
          <Plus size={14} className="text-accent" />
        </IconButton>
      </div>
      {rows.length === 0 && <span className="text-[12px] text-dim opacity-60">none</span>}
      {rows.map((row, i) => (
        <div key={i} className="flex w-full items-center gap-2">
          <TextInput
            value={row.k}
            placeholder={keyPlaceholder}
            onChange={(e) => update(i, { k: e.target.value })}
            className="flex-1"
          />
          {valueOptions ? (
            <Select
              options={valueOptions}
              value={valueOptions.includes(row.v) ? row.v : ''}
              allowEmpty
              onChange={(e) => update(i, { v: e.target.value })}
              className="flex-1"
            />
          ) : (
            <TextInput
              value={row.v}
              placeholder={valuePlaceholder}
              onChange={(e) => update(i, { v: e.target.value })}
              className="flex-1"
            />
          )}
          <IconButton title="Remove" danger onClick={() => onChange(rows.filter((_, j) => j !== i))}>
            <X size={14} />
          </IconButton>
        </div>
      ))}
    </div>
  )
}

/** KVEditor rows → dict, dropping empty keys/values (parity with _kv_editor.get). */
export function kvToDict(rows: KVRow[]): Record<string, string> {
  const out: Record<string, string> = {}
  for (const { k, v } of rows) {
    const key = k.trim()
    if (key && v !== '') out[key] = v
  }
  return out
}

export function dictToKv(data: Record<string, string> | undefined): KVRow[] {
  return Object.entries(data ?? {}).map(([k, v]) => ({ k, v: String(v) }))
}
