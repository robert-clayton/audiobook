import { ArrowDown } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { clearLog } from '../api/endpoints'
import { logStore } from '../hooks/logStore'
import { useLiveLog } from '../hooks/useStatusPoll'
import { Button } from './ui/Button'
import { Kicker } from './ui/Kicker'

/** Terminal log panel: auto-scroll with pause-on-scroll-up + jump chip. */
export function LogTerminal() {
  const lines = useLiveLog()
  const scrollRef = useRef<HTMLDivElement>(null)
  const [following, setFollowing] = useState(true)
  const [missed, setMissed] = useState(0)

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
  }, [lines])

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
        <Kicker>live log</Kicker>
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
            px-3 py-2 text-[12px] leading-relaxed whitespace-pre-wrap text-dim"
        >
          {lines.length === 0 ? (
            <span className="opacity-50">— log empty —</span>
          ) : (
            lines.map((line, i) => <div key={i}>{line}</div>)
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
