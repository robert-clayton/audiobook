interface Props {
  tabs: string[]
  active: string
  onChange: (tab: string) => void
}

/** Underline tabs, amber active marker. */
export function Tabs({ tabs, active, onChange }: Props) {
  return (
    <div className="flex w-full gap-1 border-b border-border" role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab}
          role="tab"
          aria-selected={tab === active}
          onClick={() => onChange(tab)}
          className={`-mb-px cursor-pointer border-b px-3 py-1.5 text-xs tracking-wide
            uppercase transition-colors duration-150
            ${
              tab === active
                ? 'border-accent text-accent'
                : 'border-transparent text-dim hover:text-text'
            }`}
        >
          {tab}
        </button>
      ))}
    </div>
  )
}
