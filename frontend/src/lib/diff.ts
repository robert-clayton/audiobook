/** Client-side unified diff (replaces the server-side difflib rendering). */

import { structuredPatch } from 'diff'

export interface DiffLine {
  kind: 'header' | 'hunk' | 'add' | 'del' | 'ctx'
  text: string
}

export interface DiffResult {
  lines: DiffLine[]
  added: number
  removed: number
}

/** Build unified-diff display lines from two texts. */
export function unifiedDiff(oldText: string, newText: string): DiffResult {
  const patch = structuredPatch('Current', 'New', oldText, newText, '', '', {
    context: 3,
  })
  const lines: DiffLine[] = []
  let added = 0
  let removed = 0

  if (patch.hunks.length === 0) return { lines, added, removed }

  lines.push({ kind: 'header', text: '--- Current' })
  lines.push({ kind: 'header', text: '+++ New' })

  for (const hunk of patch.hunks) {
    lines.push({
      kind: 'hunk',
      text: `@@ -${hunk.oldStart},${hunk.oldLines} +${hunk.newStart},${hunk.newLines} @@`,
    })
    for (const line of hunk.lines) {
      if (line.startsWith('+')) {
        added++
        lines.push({ kind: 'add', text: line })
      } else if (line.startsWith('-')) {
        removed++
        lines.push({ kind: 'del', text: line })
      } else {
        lines.push({ kind: 'ctx', text: line })
      }
    }
  }
  return { lines, added, removed }
}
