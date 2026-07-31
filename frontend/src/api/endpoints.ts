/** Typed API calls, one function per server endpoint. */

import { api, seg } from './client'
import type {
  AppConfig,
  Chapter,
  ChapterText,
  ConfigMeta,
  FailedChapter,
  FilenameFix,
  Health,
  RescrapePreview,
  SeriesDetail,
  SeriesListResponse,
  SeriesRescrapePreview,
  Speaker,
  StatusResponse,
  SubmitResponse,
} from './types'

// ── system ──────────────────────────────────────────────────────
export const getStatus = (logSince: number) =>
  api.get<StatusResponse>(`/api/status?log_since=${logSince}`)
export const getHealth = () => api.get<Health>('/api/health')
export const clearLog = () => api.post<{ ok: boolean }>('/api/log/clear')
export const syncFilesystem = () => api.post<{ ok: boolean }>('/api/sync')

// ── jobs ────────────────────────────────────────────────────────
export const startFullPipeline = () => api.post<SubmitResponse>('/api/jobs/full')
export const startScrapeAll = () => api.post<SubmitResponse>('/api/jobs/scrape-all')
export const cancelJob = (jobId: string) =>
  api.delete<{ cancelled: boolean }>(`/api/jobs/${jobId}`)

// ── series ──────────────────────────────────────────────────────
export const getSeriesList = () => api.get<SeriesListResponse>('/api/series')
export const getSeriesDetail = (name: string) =>
  api.get<SeriesDetail>(`/api/series/${seg(name)}`)
export const getChapters = (name: string) =>
  api.get<Chapter[]>(`/api/series/${seg(name)}/chapters`)
export const addSeries = (body: {
  name: string
  url: string
  latest?: string
  narrator: string
}) => api.post<{ ok: boolean; name: string }>('/api/series', body)
export const patchSeriesConfig = (name: string, body: object) =>
  api.patch<{ ok: boolean }>(`/api/series/${seg(name)}/config`, body)
export const scrapeSeries = (name: string) =>
  api.post<SubmitResponse>(`/api/series/${seg(name)}/scrape`)
export const generateSeries = (name: string) =>
  api.post<SubmitResponse>(`/api/series/${seg(name)}/generate`)
export const resyncSeries = (name: string) =>
  api.post<{ ok: boolean }>(`/api/series/${seg(name)}/resync`)
export const rescrapeSeriesPreview = (name: string) =>
  api.post<SeriesRescrapePreview>(`/api/series/${seg(name)}/rescrape-preview`)
export const rescrapeSeriesApply = (
  name: string,
  chapters: { chapter_id: number; new_text: string }[],
) => api.post<{ applied: number }>(`/api/series/${seg(name)}/rescrape-apply`, { chapters })
export const scanFilenameFixes = (name: string) =>
  api.post<{ fixes: FilenameFix[] }>(`/api/series/${seg(name)}/filename-fixes/scan`)
export const applyFilenameFixes = (name: string, chapterIds: number[]) =>
  api.post<{ renamed: number }>(`/api/series/${seg(name)}/filename-fixes/apply`, {
    chapter_ids: chapterIds,
  })

// ── chapters ────────────────────────────────────────────────────
export const getFailed = (series?: string | null) =>
  api.get<FailedChapter[]>(series ? `/api/failed?series=${seg(series)}` : '/api/failed')
export const getChapterText = (id: number, series: string) =>
  api.get<ChapterText>(`/api/chapters/${id}/text?series=${seg(series)}`)
export const putChapterText = (
  id: number,
  body: { series: string; text: string; regenerate: boolean },
) => api.put<{ ok: boolean } & Partial<SubmitResponse>>(`/api/chapters/${id}/text`, body)
export const regenerateChapter = (id: number, series: string, title?: string) =>
  api.post<SubmitResponse>(`/api/chapters/${id}/regenerate`, { series, title })
export const regenerateBulk = (chapters: { id: number; series: string; title?: string }[]) =>
  api.post<{ queued: number; requested: number }>('/api/chapters/regenerate-bulk', { chapters })
export const rescrapeChapterPreview = (id: number, series: string) =>
  api.post<RescrapePreview>(`/api/chapters/${id}/rescrape-preview`, { series })
export const rescrapeChapterApply = (id: number, series: string, newText: string) =>
  api.post<{ ok: boolean }>(`/api/chapters/${id}/rescrape-apply`, {
    series,
    new_text: newText,
  })

// ── speakers ────────────────────────────────────────────────────
export const getSpeakers = () => api.get<Speaker[]>('/api/speakers')
export const getTranscript = (name: string) =>
  api.get<{ text: string }>(`/api/speakers/${seg(name)}/transcript`)
export const putTranscript = (name: string, text: string) =>
  api.put<{ ok: boolean }>(`/api/speakers/${seg(name)}/transcript`, { text })

// ── config ──────────────────────────────────────────────────────
export const getConfig = () => api.get<AppConfig>('/api/config')
export const getConfigMeta = () => api.get<ConfigMeta>('/api/config/meta')
export const putNarrators = (
  narrators: Record<string, { pause?: number | null; volume?: number | null }>,
) => api.put<{ ok: boolean }>('/api/config/narrators', { narrators })
export const putTtsSettings = (body: { tts_batch_size?: number; tts_verbose?: boolean }) =>
  api.put<{ ok: boolean }>('/api/config/tts', body)
