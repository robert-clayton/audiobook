interface Props {
  label: string
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
}

/** Industrial toggle: squared track, amber when on. */
export function Switch({ label, checked, onChange, disabled }: Props) {
  return (
    <label
      className={`inline-flex items-center gap-2 select-none
        ${disabled ? 'cursor-not-allowed opacity-40' : 'cursor-pointer'}`}
    >
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative h-4 w-8 rounded-sm border transition-colors duration-150
          ${checked ? 'border-accent bg-accent/20' : 'border-border-strong bg-bg'}`}
      >
        <span
          className={`absolute top-1/2 h-2.5 w-2.5 -translate-y-1/2 rounded-sm
            transition-all duration-150
            ${checked ? 'left-[18px] bg-accent' : 'left-[3px] bg-dim'}`}
        />
      </button>
      <span className="text-[12px] text-text">{label}</span>
    </label>
  )
}
