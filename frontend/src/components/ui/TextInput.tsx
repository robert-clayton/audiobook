import type { InputHTMLAttributes } from 'react'

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
}

export function TextInput({ label, className = '', id, ...rest }: Props) {
  const inputId = id ?? (label ? `ti-${label.replace(/\W+/g, '-').toLowerCase()}` : undefined)
  const input = (
    <input
      id={inputId}
      className={`w-full rounded-sm border border-border bg-bg px-2.5 py-1.5 text-[13px]
        text-text placeholder:text-dim/60 read-only:opacity-60 hover:border-border-strong
        focus:border-accent focus:outline-none ${className}`}
      {...rest}
    />
  )
  if (!label) return input
  return (
    <label htmlFor={inputId} className="flex w-full flex-col gap-1">
      <span className="text-[11px] tracking-wide text-dim uppercase">{label}</span>
      {input}
    </label>
  )
}
