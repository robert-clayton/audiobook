/** Module-level log store fed by the status poll.
 *
 * Lines are parsed into typed LogItems (see lib/logParse) as they arrive;
 * raw strings are kept alongside for the Raw view. High-frequency appends
 * re-render only subscribers via useSyncExternalStore, and the transport
 * (polling today, SSE later) stays hidden behind this interface.
 */

import { annotate, parseLine, type LogItem } from '../lib/logParse'

const MAX_LINES = 500

let items: LogItem[] = []
let raw: string[] = []
let seq = 0
let nextId = 1
let version = 0
const listeners = new Set<() => void>()

function notify() {
  version++
  for (const l of listeners) l()
}

export const logStore = {
  subscribe(listener: () => void) {
    listeners.add(listener)
    return () => listeners.delete(listener)
  },
  getVersion: () => version,
  getItems: () => items,
  getRaw: () => raw,
  getSeq: () => seq,
  append(newLines: string[], newSeq: number) {
    // Idempotent by seq: several components can observe the same poll result
    // (shared query cache, one effect each) — only the first append lands.
    if (newSeq <= seq) return
    seq = newSeq
    if (!newLines.length) return

    raw = [...raw, ...newLines].slice(-MAX_LINES)

    const appended = [...items]
    const startAt = appended.length
    for (const line of newLines) {
      const parsed = parseLine(line)
      if (parsed) appended.push({ ...parsed, id: nextId++ })
    }
    annotate(appended, startAt)
    items = appended.slice(-MAX_LINES)
    notify()
  },
  clear() {
    items = []
    raw = []
    notify()
  },
}
