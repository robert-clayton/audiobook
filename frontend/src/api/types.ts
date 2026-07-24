/** DTOs mirroring audiobook/server/routers responses (verified via smoke tests). */

export interface JobProgress {
  phase?: string
  series?: string
  series_idx?: number
  series_total?: number
  chapter?: string
  raw_path?: string
  pct?: number
}

export interface JobSnapshot {
  id: string
  type: string
  label: string
  series: string | null
  chapter_id: number | null
  chapter_title: string | null
  status: 'queued' | 'running' | 'done' | 'failed' | 'cancelled'
  created_at: number
  started_at: number | null
  finished_at: number | null
  error: string
  progress: JobProgress
}

export interface QueueSnapshot {
  current: JobSnapshot | null
  queued: JobSnapshot[]
  history: JobSnapshot[]
}

export interface StatusResponse {
  state: string
  error: string
  busy: boolean
  dev_mode: boolean
  queue: QueueSnapshot
  log: { lines: string[]; seq: number }
}

export interface SubmitResponse {
  job: JobSnapshot
  created: boolean
}

export interface Health {
  share_ok: boolean
  disk_free_gb?: number
  db_size_mb?: number
  vram_used_gb?: number
  vram_total_gb?: number
  model_loaded: boolean
}

export interface SeriesRow {
  name: string
  done: number
  pending: number
  processing: number
  failed: number
  narrator: string
  url: string
}

export interface SeriesStats {
  done_count: number
  tracked_hours: number
  done_7d: number
  done_30d: number
}

export interface SeriesListResponse {
  series: SeriesRow[]
  stats: SeriesStats | null
}

export interface SystemConfig {
  voice?: string | null
  modulate?: boolean
  speed?: number
  type?: string[]
}

export interface SeriesConfigEntry {
  name: string
  url: string
  narrator?: string
  latest?: string
  enabled?: boolean
  replacements?: Record<string, string>
  mappings?: Record<string, string>
  system?: SystemConfig
}

export interface SeriesDetail {
  name: string
  narrator: string | null
  source: string | null
  summary: { pending: number; processing: number; done: number; failed: number }
  config: SeriesConfigEntry | null
}

export interface Chapter {
  id: number
  title: string
  status: string
  published_date: string
  error: string
  raw_path: string
  pct: number | null
}

export interface ChapterText {
  title: string
  status: string
  text: string
  cleaned: string
}

export interface FailedChapter {
  id: number
  series: string
  title: string
  error: string
  retries: number
  updated_at: string
}

export interface Speaker {
  name: string
  duration_s: number | null
  has_transcript: boolean
  used_by: string[]
}

export interface ConfigMeta {
  speakers: string[]
  system_types: string[]
  sources: string[]
}

export interface RescrapePreview {
  old_text: string
  new_text: string
  source_url: string
}

export interface SeriesRescrapeChange {
  chapter_id: number
  title: string
  source_url: string
  old_text: string
  new_text: string
}

export interface SeriesRescrapeUnavailable {
  chapter_id: number
  title: string
  source_url: string
}

export interface SeriesRescrapePreview {
  changes: SeriesRescrapeChange[]
  unavailable: SeriesRescrapeUnavailable[]
}

export interface FilenameFix {
  chapter_id: number
  old_title: string
  new_title: string
}

export interface AppConfig {
  config: {
    output_dir: string
    tts_engine?: string
    narrators?: Record<string, { pause?: number; volume?: number }>
    [key: string]: unknown
  }
  series: SeriesConfigEntry[]
}
