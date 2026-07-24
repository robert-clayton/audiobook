import { useQuery } from '@tanstack/react-query'
import { keepPreviousData } from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { getSeriesList, startFullPipeline, startScrapeAll, syncFilesystem } from '../api/endpoints'
import { ApiError } from '../api/client'
import { seg } from '../api/client'
import type { SeriesRow } from '../api/types'
import { HealthStrip } from '../components/HealthStrip'
import { LogTerminal } from '../components/LogTerminal'
import { PageHeader } from '../components/PageHeader'
import { QueuePanel } from '../components/QueuePanel'
import { SearchInput } from '../components/SearchInput'
import { DataTable } from '../components/table/DataTable'
import { Button } from '../components/ui/Button'
import { EmptyState } from '../components/ui/EmptyState'
import { Kicker } from '../components/ui/Kicker'
import { AddSeriesDialog } from '../components/dialogs/AddSeriesDialog'
import { NarratorSettingsDialog } from '../components/dialogs/NarratorSettingsDialog'
import { useStatus } from '../hooks/useStatusPoll'
import { useSubmitJob } from '../hooks/useSubmitJob'
import { POLL_FAST, qk } from '../lib/queryKeys'

export function DashboardPage() {
  const status = useStatus()
  const submitJob = useSubmitJob()
  const navigate = useNavigate()
  const [filter, setFilter] = useState('')
  const [addOpen, setAddOpen] = useState(false)
  const [narratorsOpen, setNarratorsOpen] = useState(false)
  const [syncing, setSyncing] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: qk.series,
    queryFn: getSeriesList,
    refetchInterval: POLL_FAST,
    placeholderData: keepPreviousData,
  })

  const columns = useMemo<ColumnDef<SeriesRow>[]>(
    () => [
      {
        accessorKey: 'name',
        header: 'Series',
        cell: ({ row }) => (
          <Link
            to={`/series/${seg(row.original.name)}`}
            onClick={(e) => e.stopPropagation()}
            className="font-medium text-accent hover:underline"
          >
            {row.original.name}
          </Link>
        ),
      },
      {
        accessorKey: 'done',
        header: 'Done',
        size: 80,
        meta: { align: 'center' },
        cell: ({ row }) => (
          <span className={row.original.done ? 'text-success' : 'text-dim'}>
            {row.original.done}
          </span>
        ),
      },
      {
        accessorKey: 'pending',
        header: 'Pending',
        size: 80,
        meta: { align: 'center' },
        cell: ({ row }) => (
          <span className={row.original.pending ? 'text-info' : 'text-dim'}>
            {row.original.pending}
          </span>
        ),
      },
      {
        accessorKey: 'failed',
        header: 'Failed',
        size: 80,
        meta: { align: 'center' },
        cell: ({ row }) =>
          row.original.failed ? (
            <Link
              to={`/failed?series=${seg(row.original.name)}`}
              onClick={(e) => e.stopPropagation()}
              className="text-error underline"
            >
              {row.original.failed}
            </Link>
          ) : (
            <span className="text-dim">0</span>
          ),
      },
      {
        accessorKey: 'narrator',
        header: 'Narrator',
        cell: ({ row }) => <span className="text-dim">{row.original.narrator}</span>,
      },
    ],
    [],
  )

  const stats = data?.stats
  const busy = status?.busy ?? false

  const doSync = async () => {
    setSyncing(true)
    try {
      await syncFilesystem()
      toast.success('Sync complete')
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Sync failed')
    } finally {
      setSyncing(false)
    }
  }

  return (
    <>
      <PageHeader
        title="Audiobook Pipeline"
        nav={[
          { label: 'failed', to: '/failed' },
          { label: 'speakers', to: '/speakers' },
        ]}
      />

      <div className="flex w-full flex-wrap items-center justify-between gap-2">
        <HealthStrip />
        {stats && (
          <span className="text-[11px] text-dim">
            {stats.done_count} chapters
            <span className="mx-2 opacity-30">|</span>
            {stats.tracked_hours.toFixed(1)} h tracked audio
            <span className="mx-2 opacity-30">|</span>
            {stats.done_7d} last 7d, {stats.done_30d} last 30d
          </span>
        )}
      </div>

      <div className="flex w-full flex-wrap items-center gap-2">
        <Button variant="accent" onClick={() => submitJob.mutate(startFullPipeline)}>
          Run Full Pipeline
        </Button>
        <Button onClick={() => submitJob.mutate(startScrapeAll)}>Scrape Only</Button>
        <Button disabled={busy || syncing} onClick={() => void doSync()}>
          {syncing ? 'Syncing…' : 'Sync Filesystem'}
        </Button>
        <Button variant="success" onClick={() => setAddOpen(true)}>
          Add Series
        </Button>
        <Button onClick={() => setNarratorsOpen(true)}>Narrators</Button>
      </div>

      <QueuePanel status={status} />

      <section className="flex w-full flex-col gap-1.5">
        <div className="flex w-full items-center justify-between">
          <Kicker>series</Kicker>
          <SearchInput value={filter} onChange={setFilter} placeholder="filter series…" />
        </div>
        <DataTable
          columns={columns}
          data={data?.series ?? []}
          isLoading={isLoading}
          defaultSort={[{ id: 'name', desc: false }]}
          pageSize={10}
          globalFilter={filter}
          getRowId={(r) => r.name}
          onRowClick={(r) => navigate(`/series/${seg(r.name)}`)}
          emptyState={<EmptyState>no series configured</EmptyState>}
        />
      </section>

      <LogTerminal />

      <AddSeriesDialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onAdded={(name) => navigate(`/series/${seg(name)}`)}
      />
      <NarratorSettingsDialog open={narratorsOpen} onClose={() => setNarratorsOpen(false)} />
    </>
  )
}
