import { ArrowDown, Check } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { clearLog } from '../api/endpoints'
import { logStore } from '../hooks/logStore'
import { useLiveLog } from '../hooks/useStatusPoll'
import type { LogItem } from '../lib/logParse'
import { Button } from './ui/Button'
import { Kicker } from './ui/Kicker'

type Mode = 'compact' | 'all' | 'raw'
const MODES: Mode[] = ['compact', 'all', 'raw']
const MODE_KEY = 'audiobook.logMode'

const KIND_COLORS: Record<LogItem['kind'], string> = {
  queue: 'var(--color-info)',
  series: 'var(--color-accent)',
  chapter: 'var(--color-text)',
  step: 'var(--color-dim)',
  timing: 'var(--color-dim)',
  warn: 'var(--color-warning)',
  error: 'var(--color-error)',
  sync: 'var(--color-info)',
  info: 'var(--color-dim)',
}

/** Compact mode: structural items only — no per-step chatter, no timing
 * lines, no scrape entries that yielded nothing. */
function visibleInCompact(it: LogItem): boolean {
  if (it.kind === 'step' || it.kind === 'timing' || it.kind === 'info') return false
  if (it.kind === 'series' && it.empty) return false
  return true
}

function Row({ it }: { it: LogItem }) {
  const color = KIND_COLORS[it.kind]
  const indent = it.kind === 'chapter' ? 'pl-5' : it.kind === 'step' || it.kind === 'timing' ? 'pl-10' : ''
  return (
    <div className={`flex items-baseline gap-2 px-1 py-px ${indent}`}>
      <span
        className="inline-block h-1.5 w-1.5 shrink-0 self-center rounded-full"
        style={{ background: color, boxShadow: it.kind === 'error' || it.kind === 'warn' ? `0 0 4px ${color}` : undefined }}
      />
      {it.kind === 'series' && (
        <span className="shrink-0 text-[10px] text-dim tabular-nums">
          [{it.index}/{it.total}]
        </span>
      )}
      {it.kind === 'series' && (
        <span className="shrink-0 text-[10px] tracking-wide uppercase" style={{ color }}>
          {it.phase}
        </span>
      )}
      <span className="min-w-0 break-words" style={{ color: it.kind === 'series' ? 'var(--color-text)' : color }}>
        {it.text}
      </span>
      {it.ok && <Check size={12} className="shrink-0 self-center text-success" />}
    </div>
  )
}

/** Structured live-log panel: parsed, colorized items with Compact/All/Raw modes. */
export function LogTerminal() {
  const { items, raw } = useLiveLog()
  const [mode, setMode] = useState<Mode>(() => {
    const m = localStorage.getItem(MODE_KEY)
    return m === 'all' || m === 'raw' ? m : 'compact'
  })
  const scrollRef = useRef<HTMLDivElement>(null)
  const [following, setFollowing] = useState(true)
  const [missed, setMissed] = useState(0)

  const shown =
    mode === 'raw' ? null : mode === 'all' ? items : items.filter(visibleInCompact)
  const lineCount = mode === 'raw' ? raw.length : (shown?.length ?? 0)

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    if (following) {
      el.scrollTop = el.scrollHeight
      setMissed(0)
    } else {
      setMissed((m) => m + 1)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lineCount, mode])

  const onScroll = () => {
    const el = scrollRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24
    if (atBottom !== following) {
      setFollowing(atBottom)
      if (atBottom) setMissed(0)
    }
  }

  const jumpToLatest = () => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
    setFollowing(true)
    setMissed(0)
  }

  return (
    <section className="w-full">
      <div className="flex w-full items-center justify-between">
        <span className="flex items-center gap-3">
          <Kicker>live log</Kicker>
          <span className="flex gap-0.5">
            {MODES.map((m) => (
              <button
                key={m}
                onClick={() => {
                  setMode(m)
                  localStorage.setItem(MODE_KEY, m)
                }}
                className={`cursor-pointer rounded-sm border px-1.5 py-px text-[10px]
                  tracking-wide uppercase transition-colors duration-150
                  ${
                    mode === m
                      ? 'border-accent text-accent'
                      : 'border-transparent text-dim hover:text-text'
                  }`}
              >
                {m}
              </button>
            ))}
          </span>
        </span>
        <Button
          variant="ghost"
          onClick={() => {
            void clearLog()
            logStore.clear()
          }}
        >
          Clear
        </Button>
      </div>
      <div className="relative w-full">
        <div
          ref={scrollRef}
          onScroll={onScroll}
          className="h-64 w-full overflow-y-auto rounded-sm border border-border bg-bg
            px-2 py-1.5 text-[12px] leading-relaxed"
        >
          {lineCount === 0 ? (
            <span className="px-1 text-dim opacity-50">— log empty —</span>
          ) : mode === 'raw' ? (
            raw.map((line, i) => (
              <div key={i} className="px-1 whitespace-pre-wrap text-dim">
                {line}
              </div>
            ))
          ) : (
            shown!.map((it) => <Row key={it.id} it={it} />)
          )}
        </div>
        {!following && (
          <button
            onClick={jumpToLatest}
            className="absolute right-3 bottom-3 flex cursor-pointer items-center gap-1
              rounded-sm border border-accent bg-bg px-2 py-1 text-[11px] text-accent
              transition-colors duration-150 hover:bg-accent/10"
          >
            <ArrowDown size={12} />
            latest{missed > 0 ? ` (${missed} new)` : ''}
          </button>
        )}
      </div>
    </section>
  )
}
