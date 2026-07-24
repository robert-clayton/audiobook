/** Module-level log ring buffer fed by the status poll.
 *
 * Log lines never touch React Query — high-frequency appends re-render only
 * LogTerminal subscribers via useSyncExternalStore. The transport (polling
 * today, SSE later) is hidden behind this store interface.
 */

const MAX_LINES = 500

let lines: string[] = []
let seq = 0
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
  getLines: () => lines,
  getSeq: () => seq,
  append(newLines: string[], newSeq: number) {
    // Idempotent by seq: several components can observe the same poll result
    // (shared query cache, one effect each) — only the first append lands.
    if (newSeq <= seq) return
    seq = newSeq
    if (newLines.length) {
      lines = [...lines, ...newLines].slice(-MAX_LINES)
      notify()
    }
  },
  clear() {
    lines = []
    notify()
  },
}
