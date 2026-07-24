import type { DiffLine } from '../lib/diff'

const KIND_STYLES: Record<DiffLine['kind'], string> = {
  header: 'text-dim opacity-70',
  hunk: 'text-info mt-2',
  add: 'bg-success/10 text-success',
  del: 'bg-error/10 text-error',
  ctx: 'text-dim',
}

export function DiffView({ lines }: { lines: DiffLine[] }) {
  return (
    <pre className="w-full overflow-x-auto rounded-sm border border-border bg-bg p-3 text-[12px] leading-relaxed">
      {lines.map((line, i) => (
        <div key={i} className={`px-1 whitespace-pre-wrap ${KIND_STYLES[line.kind]}`}>
          {line.text || ' '}
        </div>
      ))}
    </pre>
  )
}

/** `+N / −N lines` header helper. */
export function DiffStats({ added, removed }: { added: number; removed: number }) {
  return (
    <span className="text-[12px] whitespace-nowrap">
      <span className="text-success">+{added}</span>
      <span className="mx-1 text-dim">/</span>
      <span className="text-error">-{removed}</span>
      <span className="ml-1 text-dim">lines</span>
    </span>
  )
}
