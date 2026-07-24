import type { SelectHTMLAttributes } from 'react'

interface Props extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  options: string[]
  /** Adds an empty option (e.g. clearable voice select). */
  allowEmpty?: boolean
  emptyLabel?: string
}

export function Select({
  label,
  options,
  allowEmpty,
  emptyLabel = '—',
  className = '',
  id,
  ...rest
}: Props) {
  const selectId = id ?? (label ? `sel-${label.replace(/\W+/g, '-').toLowerCase()}` : undefined)
  const select = (
    <select
      id={selectId}
      className={`w-full cursor-pointer rounded-sm border border-border bg-bg px-2 py-1.5
        text-[13px] text-text hover:border-border-strong focus:border-accent
        focus:outline-none ${className}`}
      {...rest}
    >
      {allowEmpty && <option value="">{emptyLabel}</option>}
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  )
  if (!label) return select
  return (
    <label htmlFor={selectId} className="flex w-full flex-col gap-1">
      <span className="text-[11px] tracking-wide text-dim uppercase">{label}</span>
      {select}
    </label>
  )
}
