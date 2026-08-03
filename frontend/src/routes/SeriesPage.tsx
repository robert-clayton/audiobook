import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { BookOpen, RefreshCw, RotateCw } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { ApiError } from '../api/client'
import {
  generateSeries,
  getChapters,
  getSeriesDetail,
  regenerateChapter,
  rescrapeChapterPreview,
  rescrapeSeriesPreview,
  resyncSeries,
  scanFilenameFixes,
  scrapeSeries,
} from '../api/endpoints'
import type { Chapter, FilenameFix, RescrapePreview, SeriesRescrapePreview } from '../api/types'
import { LogTerminal } from '../components/LogTerminal'
import { PageHeader } from '../components/PageHeader'
import { QueuePanel } from '../components/QueuePanel'
import { SearchInput } from '../components/SearchInput'
import { StatusDot } from '../components/StatusDot'
import { DataTable } from '../components/table/DataTable'
import { ChapterDialog } from '../components/dialogs/ChapterDialog'
import { FixFilenamesDialog } from '../components/dialogs/FixFilenamesDialog'
import { RescrapeDiffDialog } from '../components/dialogs/RescrapeDiffDialog'
import { RescrapeSeriesDialog } from '../components/dialogs/RescrapeSeriesDialog'
import { SeriesEditorDialog } from '../components/dialogs/SeriesEditorDialog'
import { Button } from '../components/ui/Button'
import { EmptyState } from '../components/ui/EmptyState'
import { IconButton } from '../components/ui/IconButton'
import { Kicker } from '../components/ui/Kicker'
import { useStatus } from '../hooks/useStatusPoll'
import { useSubmitJob } from '../hooks/useSubmitJob'
import { naturalSort } from '../lib/naturalSort'
import { POLL_FAST, qk } from '../lib/queryKeys'

export function SeriesPage() {
  const { name = '' } = useParams()
  const status = useStatus()
  const submitJob = useSubmitJob()
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const filter = params.get('q') ?? ''

  // Dialog state
  const [openChapter, setOpenChapter] = useState<Chapter | null>(null)
  const [rescrapeTarget, setRescrapeTarget] = useState<Chapter | null>(null)
  const [rescrapePrev, setRescrapePrev] = useState<RescrapePreview | null>(null)
  const [seriesPreview, setSeriesPreview] = useState<SeriesRescrapePreview | null>(null)
  const [filenameFixes, setFilenameFixes] = useState<FilenameFix[] | null>(null)
  const [editorOpen, setEditorOpen] = useState(false)
  const [pendingAction, setPendingAction] = useState<string | null>(null)

  const detail = useQuery({
    queryKey: qk.seriesDetail(name),
    queryFn: () => getSeriesDetail(name),
    refetchInterval: POLL_FAST,
    placeholderData: keepPreviousData,
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 1,
  })
  const chapters = useQuery({
    queryKey: qk.chapters(name),
    queryFn: () => getChapters(name),
    refetchInterval: POLL_FAST,
    placeholderData: keepPreviousData,
    enabled: detail.data !== undefined,
  })

  const busy = status?.busy ?? false

  const refreshChapters = () => {
    void queryClient.invalidateQueries({ queryKey: qk.chapters(name) })
    void queryClient.invalidateQueries({ queryKey: qk.seriesDetail(name) })
  }

  /** Run an interactive (non-queued) flow with a spinner + error toast. */
  const runAction = async (key: string, fn: () => Promise<void>) => {
    setPendingAction(key)
    try {
      await fn()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Request failed')
    } finally {
      setPendingAction(null)
    }
  }

  const columns = useMemo<ColumnDef<Chapter>[]>(
    () => [
      {
        accessorKey: 'title',
        header: 'Title',
        sortingFn: naturalSort,
        cell: ({ row }) => <span className="text-text">{row.original.title}</span>,
      },
      {
        accessorKey: 'status',
        header: 'Status',
        size: 140,
        meta: { align: 'center' },
        cell: ({ row }) => {
          const ch = row.original
          return (
            <span
              className="inline-flex items-center gap-1.5 text-[12px]"
              title={ch.error || undefined}
            >
              <StatusDot status={ch.status} />
              {ch.status}
              {ch.pct != null && <span className="text-accent">{ch.pct}%</span>}
            </span>
          )
        },
      },
      {
        accessorKey: 'published_date',
        header: 'Published',
        size: 110,
        meta: { align: 'center' },
        cell: ({ row }) => <span className="text-dim">{row.original.published_date}</span>,
      },
      {
        id: 'actions',
        header: 'Actions',
        size: 110,
        meta: { align: 'center' },
        enableSorting: false,
        cell: ({ row }) => {
          const ch = row.original
          return (
            <span className="inline-flex items-center gap-0.5">
              <IconButton title="Open chapter" onClick={() => setOpenChapter(ch)}>
                <BookOpen size={14} />
              </IconButton>
              <IconButton
                title="Rescrape from source"
                disabled={busy}
                onClick={() =>
                  void runAction(`rescrape-${ch.id}`, async () => {
                    toast.info(`Fetching: ${ch.title}…`)
                    const prev = await rescrapeChapterPreview(ch.id, name)
                    if (prev.old_text === prev.new_text) {
                      toast.info('No changes detected')
                      return
                    }
                    setRescrapeTarget(ch)
                    setRescrapePrev(prev)
                  })
                }
              >
                <RefreshCw size={14} />
              </IconButton>
              <IconButton
                title="Regenerate audio"
                onClick={() =>
                  submitJob.mutate(() => regenerateChapter(ch.id, name, ch.title))
                }
              >
                <RotateCw size={14} />
              </IconButton>
            </span>
          )
        },
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [name, busy],
  )

  if (detail.error instanceof ApiError && detail.error.status === 404) {
    return (
      <>
        <PageHeader title={name} backTo="/" />
        <EmptyState>series "{name}" not found</EmptyState>
        <Link to="/" className="text-[13px] text-accent hover:underline">
          back to dashboard
        </Link>
      </>
    )
  }

  const info = detail.data
  const summary = info?.summary

  return (
    <>
      <PageHeader title={name} backTo="/" />

      {info && (
        <p className="w-full text-[12px] text-dim">
          <span className="opacity-60">narrator:</span> {info.narrator ?? 'N/A'}
          <span className="mx-2.5 opacity-30">|</span>
          <span className="opacity-60">source:</span> {info.source ?? 'N/A'}
          {summary && (
            <>
              <span className="mx-2.5 opacity-30">|</span>
              {summary.done} done, {summary.pending} pending, {summary.failed} failed
            </>
          )}
        </p>
      )}

      <div className="flex w-full flex-wrap items-center gap-2">
        <Button variant="accent" onClick={() => submitJob.mutate(() => scrapeSeries(name))}>
          Scrape
        </Button>
        <Button variant="accent" onClick={() => submitJob.mutate(() => generateSeries(name))}>
          Generate
        </Button>
        <Button
          disabled={busy || pendingAction === 'rescrape-series'}
          onClick={() =>
            void runAction('rescrape-series', async () => {
              toast.info('Checking all chapters — this can take a while…')
              const prev = await rescrapeSeriesPreview(name)
              if (!prev.changes.length && !prev.unavailable.length) {
                toast.info('No changes detected')
                return
              }
              setSeriesPreview(prev)
            })
          }
        >
          {pendingAction === 'rescrape-series' ? 'Checking…' : 'Rescrape Series'}
        </Button>
        <Button
          disabled={busy || pendingAction === 'fix-filenames'}
          onClick={() =>
            void runAction('fix-filenames', async () => {
              const res = await scanFilenameFixes(name)
              if (!res.fixes.length) {
                toast.info('No filenames to fix')
                return
              }
              setFilenameFixes(res.fixes)
            })
          }
        >
          {pendingAction === 'fix-filenames' ? 'Scanning…' : 'Fix Filenames'}
        </Button>
        <Button
          disabled={busy || pendingAction === 'resync'}
          onClick={() =>
            void runAction('resync', async () => {
              await resyncSeries(name)
              refreshChapters()
              toast.success('Resync complete')
            })
          }
        >
          {pendingAction === 'resync' ? 'Resyncing…' : 'Resync Filesystem'}
        </Button>
        <Button onClick={() => setEditorOpen(true)}>Edit Config</Button>
      </div>

      <QueuePanel status={status} />

      <section className="flex w-full flex-col gap-1.5">
        <div className="flex w-full items-center justify-between">
          <Kicker>chapters</Kicker>
          <SearchInput
            value={filter}
            onChange={(v) => {
              setParams(
                (p) => {
                  if (v) p.set('q', v)
                  else p.delete('q')
                  return p
                },
                { replace: true },
              )
            }}
            placeholder="filter chapters…"
          />
        </div>
        <DataTable
          columns={columns}
          data={chapters.data ?? []}
          isLoading={chapters.isLoading}
          pageSize={20}
          globalFilter={filter}
          tableId="chapters"
          getRowId={(r) => String(r.id)}
          emptyState={<EmptyState>no chapters — scrape or drop raws and resync</EmptyState>}
        />
      </section>

      <LogTerminal />

      <ChapterDialog
        chapter={openChapter}
        series={name}
        onClose={() => setOpenChapter(null)}
        onSaved={refreshChapters}
      />
      <RescrapeDiffDialog
        chapter={rescrapeTarget}
        preview={rescrapePrev}
        series={name}
        onClose={() => {
          setRescrapeTarget(null)
          setRescrapePrev(null)
        }}
        onApplied={refreshChapters}
      />
      {seriesPreview && (
        <RescrapeSeriesDialog
          series={name}
          preview={seriesPreview}
          onClose={() => setSeriesPreview(null)}
          onApplied={refreshChapters}
        />
      )}
      {filenameFixes && (
        <FixFilenamesDialog
          series={name}
          fixes={filenameFixes}
          onClose={() => setFilenameFixes(null)}
          onApplied={refreshChapters}
        />
      )}
      <SeriesEditorDialog
        open={editorOpen}
        seriesConfig={info?.config ?? null}
        onClose={() => setEditorOpen(false)}
        onSaved={refreshChapters}
      />
    </>
  )
}
