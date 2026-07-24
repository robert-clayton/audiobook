/** Single source of truth for TanStack Query keys and polling cadence. */

export const qk = {
  status: ['status'] as const,
  health: ['health'] as const,
  series: ['series'] as const,
  seriesDetail: (name: string) => ['series', name] as const,
  chapters: (name: string) => ['chapters', name] as const,
  failed: (filter: string | null) => ['failed', filter ?? 'all'] as const,
  speakers: ['speakers'] as const,
  config: ['config'] as const,
  configMeta: ['configMeta'] as const,
  chapterText: (id: number) => ['chapterText', id] as const,
}

/** Polling intervals (ms) — match the legacy NiceGUI cadence. */
export const POLL_FAST = 2000
export const POLL_SLOW = 10000
