interface Props {
  label?: string
  value: number | null
  onChange: (value: number | null) => void
  min?: number
  max?: number
  step?: number
  placeholder?: string
  className?: string
}

/** Nullable number field — empty string maps to null (per-narrator overrides). */
export function NumberInput({
  label,
  value,
  onChange,
  min,
  max,
  step,
  placeholder,
  className = '',
}: Props) {
  const input = (
    <input
      type="number"
      value={value ?? ''}
      min={min}
      max={max}
      step={step}
      placeholder={placeholder}
      onChange={(e) => {
        const raw = e.target.value
        onChange(raw === '' ? null : Number(raw))
      }}
      className={`w-full rounded-sm border border-border bg-bg px-2.5 py-1.5 text-[13px]
        text-text placeholder:text-dim/60 hover:border-border-strong focus:border-accent
        focus:outline-none ${className}`}
    />
  )
  if (!label) return input
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] tracking-wide text-dim uppercase">{label}</span>
      {input}
    </label>
  )
}
