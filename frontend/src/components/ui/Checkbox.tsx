import { Check, Minus } from 'lucide-react'

interface Props {
  checked: boolean
  indeterminate?: boolean
  onChange: (checked: boolean) => void
  label?: string
  disabled?: boolean
}

export function Checkbox({ checked, indeterminate, onChange, label, disabled }: Props) {
  return (
    <label
      className={`inline-flex items-center gap-2 select-none
        ${disabled ? 'cursor-not-allowed opacity-40' : 'cursor-pointer'}`}
    >
      <button
        type="button"
        role="checkbox"
        aria-checked={indeterminate ? 'mixed' : checked}
        disabled={disabled}
        onClick={(e) => {
          e.stopPropagation()
          onChange(!checked)
        }}
        className={`flex h-3.5 w-3.5 items-center justify-center rounded-sm border
          transition-colors duration-150
          ${checked || indeterminate ? 'border-accent bg-accent/20 text-accent' : 'border-border-strong bg-bg text-transparent hover:border-dim'}`}
      >
        {indeterminate ? <Minus size={10} strokeWidth={3} /> : <Check size={10} strokeWidth={3} />}
      </button>
      {label && <span className="text-[12px] text-text">{label}</span>}
    </label>
  )
}
