import { Search, X } from 'lucide-react'
import { useEffect, useRef } from 'react'

interface Props {
  value: string
  onChange: (value: string) => void
  placeholder?: string
}

/** Filter input with `/` focus shortcut and Esc-to-clear. */
export function SearchInput({ value, onChange, placeholder = 'filter…' }: Props) {
  const ref = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (
        e.key === '/' &&
        !(e.target instanceof HTMLInputElement) &&
        !(e.target instanceof HTMLTextAreaElement)
      ) {
        e.preventDefault()
        ref.current?.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className="relative w-64 max-w-full">
      <Search size={13} className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-dim" />
      <input
        ref={ref}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            onChange('')
            ref.current?.blur()
          }
        }}
        className="w-full rounded-sm border border-border bg-bg py-1.5 pr-7 pl-8 text-[13px]
          text-text placeholder:text-dim/60 hover:border-border-strong
          focus:border-accent focus:outline-none"
      />
      {value && (
        <button
          onClick={() => onChange('')}
          className="absolute top-1/2 right-2 -translate-y-1/2 cursor-pointer text-dim hover:text-text"
          title="Clear"
        >
          <X size={13} />
        </button>
      )}
    </div>
  )
}
