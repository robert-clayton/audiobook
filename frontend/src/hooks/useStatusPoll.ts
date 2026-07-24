/** The single 2s poll powering the state badge, queue panel, and log feed. */

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useSyncExternalStore } from 'react'
import { toast } from 'sonner'
import { getStatus } from '../api/endpoints'
import type { JobSnapshot, StatusResponse } from '../api/types'
import { POLL_FAST, qk } from '../lib/queryKeys'
import { fmtDuration } from '../lib/format'
import { logStore } from './logStore'

export function useStatus(): StatusResponse | undefined {
  // Pure consumer — many components call this; the shared cache entry means
  // one network request per tick. Side effects live in useLogFeed (AppShell).
  const query = useQuery({
    queryKey: qk.status,
    queryFn: () => getStatus(logStore.getSeq()),
    refetchInterval: POLL_FAST,
  })
  return query.data
}

/** Feed polled log lines into the log store. Mount ONCE (AppShell) — the
 * store's seq guard additionally drops any duplicate delivery. */
export function useLogFeed(status: StatusResponse | undefined) {
  useEffect(() => {
    if (status) logStore.append(status.log.lines, status.log.seq)
  }, [status])
}

export function useLiveLog(): string[] {
  useSyncExternalStore(logStore.subscribe, logStore.getVersion)
  return logStore.getLines()
}

/** Toast + browser Notification when a job finishes (parity with queue_panel.py). */
export function useJobNotifications(status: StatusResponse | undefined) {
  const seenRef = useRef<Set<string> | null>(null)
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!status) return
    const history = status.queue.history

    // Seed silently from the first snapshot — only NEW completions notify.
    if (seenRef.current === null) {
      seenRef.current = new Set(history.map((j) => j.id))
      return
    }
    const seen = seenRef.current

    for (const job of history) {
      if (seen.has(job.id)) continue
      seen.add(job.id)
      notifyJob(job)
      // A finished job changes series/chapter/failed data — refresh promptly.
      queryClient.invalidateQueries({ queryKey: qk.series })
      queryClient.invalidateQueries({ queryKey: ['chapters'] })
      queryClient.invalidateQueries({ queryKey: ['failed'] })
    }
  }, [status, queryClient])
}

function notifyJob(job: JobSnapshot) {
  const took =
    job.started_at && job.finished_at ? ` (${fmtDuration(job.finished_at - job.started_at)})` : ''
  if (job.status === 'done') {
    toast.success(`Done: ${job.label}${took}`)
    browserNotify('Job complete', `${job.label}${took}`)
  } else if (job.status === 'failed') {
    toast.error(`Failed: ${job.label} — ${job.error}`.slice(0, 140))
    browserNotify('Job failed', `${job.label}: ${job.error}`.slice(0, 140))
  } else if (job.status === 'cancelled') {
    toast.info(`Cancelled: ${job.label}`)
  }
}

function browserNotify(title: string, body: string) {
  if (typeof Notification === 'undefined') return
  if (Notification.permission === 'granted' && document.visibilityState !== 'visible') {
    new Notification(title, { body })
  }
}

/** Ask for browser-notification permission (called on first job submit). */
export function requestNotifyPermission() {
  if (typeof Notification !== 'undefined' && Notification.permission === 'default') {
    void Notification.requestPermission()
  }
}
