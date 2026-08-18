/** Classify pipeline log lines into typed items for the structured log view.
 *
 * The line format is stable pipeline output: series markers `[N/62] Scraping X`,
 * `[queue]`/`[sync]`/`[t]` prefixes, and tab-indented chapter headers with
 * tab-indented step lines (`Merged!`, `Saved!`, `Converted to MP3!`) beneath.
 */

export type LogKind =
  | 'queue'
  | 'series'
  | 'chapter'
  | 'step'
  | 'timing'
  | 'warn'
  | 'error'
  | 'sync'
  | 'info'

export interface LogItem {
  id: number
  raw: string
  kind: LogKind
  /** Display text (indentation and prefixes cleaned). */
  text: string
  phase?: 'scrape' | 'generate'
  index?: number
  total?: number
  /** Chapter finished (its "Converted to MP3!" arrived). */
  ok?: boolean
  /** Series entry that produced no chapters before the next entry began. */
  empty?: boolean
}

const SERIES_RE = /^\[(\d+)\/(\d+)\]\s+(Scraping|Generating)\s+(.+)$/
const QUEUE_RE = /^\[queue\]\s*(.*)$/
const STEP_RE = /^(Merged!|Saved!|Converted to MP3!)$/

// Match the ACTUAL pipeline message shapes, anchored at the start of the
// (de-indented) line, NOT keywords anywhere — a chapter is arbitrary text and
// may legitimately be titled "Error 404", "The Failed Experiment", etc.
const WARN_RE = /^(Chunk too long|Warning:)/i
const ERROR_RE =
  /^(Error on|Error merging|Error converting|Error applying|Error adjusting|Timed out|Skipping chapter|Problem text:|An unexpected error|Traceback|NetworkError)/i
// Unambiguous phrases that only appear in real failures, wherever they sit.
const ERROR_SUBSTR = /TTS produced garbled audio|share unreachable|No such file or directory|disk I\/O error/i

export function parseLine(raw: string): Omit<LogItem, 'id'> | null {
  const line = raw.replace(/\s+$/, '')
  if (!line.trim()) return null

  const indented = /^\t/.test(line)
  const text = line.replace(/^\t+/, '').trim()

  const qm = text.match(QUEUE_RE)
  if (qm) {
    // Anchor to the queue verb — a job LABEL may contain "failed"
    // (e.g. a chapter titled "The Failed Experiment").
    const kind: LogKind = /^failed\b/i.test(qm[1]) ? 'error' : 'queue'
    return { raw, kind, text: qm[1] || text }
  }

  const sm = text.match(SERIES_RE)
  if (sm) {
    return {
      raw,
      kind: 'series',
      text: sm[4],
      phase: sm[3] === 'Scraping' ? 'scrape' : 'generate',
      index: Number(sm[1]),
      total: Number(sm[2]),
    }
  }

  if (text.startsWith('[sync]')) return { raw, kind: 'sync', text: text.slice(6).trim() }
  if (text.startsWith('[t]')) return { raw, kind: 'timing', text: text.slice(3).trim() }
  if (STEP_RE.test(text)) return { raw, kind: 'step', text }
  if (text.startsWith('Regenerating:')) return { raw, kind: 'chapter', text: text.slice(13).trim() }
  if (WARN_RE.test(text)) return { raw, kind: 'warn', text }
  if (ERROR_RE.test(text) || ERROR_SUBSTR.test(text)) return { raw, kind: 'error', text }

  // Tab-indented lines that match nothing above are chapter headers
  // (arbitrary titles printed by process_chapter under a series entry).
  if (indented) return { raw, kind: 'chapter', text }

  return { raw, kind: 'info', text }
}

/** Streaming structure pass, applied as items append:
 *  - a chapter's trailing "Converted to MP3!" marks the chapter ok
 *  - a series entry with no chapter/step/warn/error before the next
 *    series/queue/sync item is marked empty (nothing new found)
 */
export function annotate(items: LogItem[], startAt: number): void {
  for (let i = Math.max(1, startAt); i < items.length; i++) {
    const it = items[i]

    if (it.kind === 'step' && it.text.startsWith('Converted')) {
      for (let j = i - 1; j >= 0 && j >= i - 30; j--) {
        if (items[j].kind === 'chapter') {
          items[j].ok = true
          break
        }
        if (items[j].kind === 'series') break
      }
    }

    if (it.kind === 'series' || it.kind === 'queue' || it.kind === 'sync') {
      for (let j = i - 1; j >= 0; j--) {
        const prev = items[j]
        if (prev.kind === 'series') {
          prev.empty = true
          break
        }
        if (prev.kind !== 'timing' && prev.kind !== 'info') break
      }
    }
  }
}
