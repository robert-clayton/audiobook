/** Small formatting helpers. */

/** Seconds → "42s" / "3m 12s" / "1h 04m". */
export function fmtDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ${String(s % 60).padStart(2, '0')}s`
  const h = Math.floor(m / 60)
  return `${h}h ${String(m % 60).padStart(2, '0')}m`
}

/** Epoch seconds → elapsed seconds from now (clock-skew safe floor of 0). */
export function elapsedSince(epochSeconds: number): number {
  return Math.max(0, Date.now() / 1000 - epochSeconds)
}

/** "2026-07-24 10:22:13" or ISO → short local display; passthrough if unparsable. */
export function fmtWhen(value: string): string {
  if (!value) return ''
  const d = new Date(value.includes('T') ? value : value.replace(' ', 'T'))
  if (isNaN(d.getTime())) return value
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function truncate(text: string, max: number): string {
  return text.length > max ? text.slice(0, max - 1) + '…' : text
}
