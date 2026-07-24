import { useMutation, useQueryClient } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { toast } from 'sonner'
import { cancelJob } from '../api/endpoints'
import type { JobSnapshot, StatusResponse } from '../api/types'
import { useElapsed } from '../hooks/useElapsed'
import { fmtDuration } from '../lib/format'
import { qk } from '../lib/queryKeys'
import { Collapsible } from './ui/Collapsible'
import { IconButton } from './ui/IconButton'
import { Kicker } from './ui/Kicker'

const JOB_STATUS_COLORS: Record<string, string> = {
  done: 'var(--color-success)',
  failed: 'var(--color-error)',
  cancelled: 'var(--color-warning)',
  running: 'var(--color-accent)',
  queued: 'var(--color-info)',
}

function useCancelJob() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: cancelJob,
    // Optimistic: drop the job from the cached snapshot immediately.
    onMutate: async (jobId: string) => {
      await queryClient.cancelQueries({ queryKey: qk.status })
      const prev = queryClient.getQueryData<StatusResponse>(qk.status)
      if (prev) {
        queryClient.setQueryData<StatusResponse>(qk.status, {
          ...prev,
          queue: {
            ...prev.queue,
            queued: prev.queue.queued.filter((j) => j.id !== jobId),
          },
        })
      }
      return { prev }
    },
    onError: (_err, _jobId, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(qk.status, ctx.prev)
      toast.error('Could not cancel job')
    },
    onSettled: () => void queryClient.invalidateQueries({ queryKey: qk.status }),
  })
}

function CurrentJob({ job }: { job: JobSnapshot }) {
  const elapsed = useElapsed(job.started_at)
  const cancel = useCancelJob()
  const p = job.progress
  const seriesCounter =
    p.series_idx != null && p.series_total != null && p.series_total > 1
      ? ` [${p.series_idx}/${p.series_total}]`
      : ''
  const cancelling = cancel.isPending

  return (
    <div className="w-full rounded-sm border border-accent/60 bg-surface">
      <div className="flex w-full items-center gap-2.5 px-3 py-2">
        <span
          className="h-2 w-2 shrink-0 rounded-full bg-accent"
          style={{ boxShadow: '0 0 6px var(--color-accent)', animation: 'pulse-dot 2s ease-in-out infinite' }}
        />
        <span className="min-w-0 truncate text-[13px] text-text">
          {job.label}
          {seriesCounter}
        </span>
        <span className="ml-auto shrink-0 text-[12px] text-dim">
          {cancelling ? 'cancelling…' : fmtDuration(elapsed)}
        </span>
        <IconButton
          title="Cancel — takes effect at the next safe checkpoint"
          danger
          disabled={cancelling}
          onClick={() => cancel.mutate(job.id)}
        >
          <X size={14} />
        </IconButton>
      </div>
      {(p.chapter || p.phase) && (
        <div className="truncate px-3 pb-1.5 text-[11px] text-dim">
          {p.phase && <span className="uppercase">{p.phase}</span>}
          {p.phase && p.chapter && <span className="mx-1.5 opacity-40">|</span>}
          {p.chapter}
          {p.pct != null && <span className="ml-1.5 text-accent">{p.pct}%</span>}
        </div>
      )}
      <div className="h-[3px] w-full overflow-hidden bg-border">
        <div
          className="h-full bg-accent transition-[width] duration-500 ease-out"
          style={{ width: `${p.pct ?? 0}%`, boxShadow: '0 0 4px var(--color-accent)' }}
        />
      </div>
    </div>
  )
}

function QueuedJob({ job }: { job: JobSnapshot }) {
  const cancel = useCancelJob()
  return (
    <div className="flex w-full items-center gap-2.5 rounded-sm border border-border bg-surface px-3 py-1.5">
      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-info" />
      <span className="min-w-0 truncate text-[12px] text-dim">{job.label}</span>
      <IconButton
        title="Remove from queue"
        danger
        className="ml-auto"
        onClick={() => cancel.mutate(job.id)}
      >
        <X size={13} />
      </IconButton>
    </div>
  )
}

export function QueuePanel({ status }: { status: StatusResponse | undefined }) {
  const queue = status?.queue
  if (!queue) return null
  const { current, queued, history } = queue
  if (!current && queued.length === 0 && history.length === 0) return null

  return (
    <section className="flex w-full flex-col gap-1.5">
      <Kicker>queue</Kicker>
      {current && <CurrentJob job={current} />}
      {queued.map((j) => (
        <QueuedJob key={j.id} job={j} />
      ))}
      {history.length > 0 && (
        <Collapsible summary={<span className="text-[12px] text-dim">history ({history.length})</span>}>
          <div className="flex w-full flex-col gap-1 py-1">
            {history.map((j) => {
              const color = JOB_STATUS_COLORS[j.status] ?? 'var(--color-dim)'
              const took =
                j.started_at && j.finished_at ? fmtDuration(j.finished_at - j.started_at) : ''
              return (
                <div key={j.id} className="flex w-full items-center gap-2 text-[12px]" title={j.error}>
                  <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: color }} />
                  <span className="min-w-0 truncate text-dim">{j.label}</span>
                  <span className="shrink-0" style={{ color }}>
                    {j.status}
                  </span>
                  {took && <span className="shrink-0 text-dim opacity-60">{took}</span>}
                </div>
              )
            })}
          </div>
        </Collapsible>
      )}
    </section>
  )
}
