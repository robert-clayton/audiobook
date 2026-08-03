import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ColumnDef, RowSelectionState } from '@tanstack/react-table'
import { RotateCw } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { ApiError } from '../api/client'
import { getFailed, regenerateBulk, regenerateChapter } from '../api/endpoints'
import type { FailedChapter } from '../api/types'
import { PageHeader } from '../components/PageHeader'
import { QueuePanel } from '../components/QueuePanel'
import { SearchInput } from '../components/SearchInput'
import { DataTable } from '../components/table/DataTable'
import { Button } from '../components/ui/Button'
import { Checkbox } from '../components/ui/Checkbox'
import { EmptyState } from '../components/ui/EmptyState'
import { IconButton } from '../components/ui/IconButton'
import { Kicker } from '../components/ui/Kicker'
import { useStatus } from '../hooks/useStatusPoll'
import { useSubmitJob } from '../hooks/useSubmitJob'
import { requestNotifyPermission } from '../hooks/useStatusPoll'
import { fmtWhen } from '../lib/format'
import { naturalSort } from '../lib/naturalSort'
import { POLL_FAST, qk } from '../lib/queryKeys'

export function FailedPage() {
  const [params] = useSearchParams()
  const seriesFilter = params.get('series')
  const status = useStatus()
  const submitJob = useSubmitJob()
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState('')
  const [selection, setSelection] = useState<RowSelectionState>({})
  const [retrying, setRetrying] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: qk.failed(seriesFilter),
    queryFn: () => getFailed(seriesFilter),
    refetchInterval: POLL_FAST,
    placeholderData: keepPreviousData,
  })

  const rows = data ?? []
  const selectedIds = Object.keys(selection).filter((id) => selection[id])

  const retrySelected = async () => {
    const chosen = rows.filter((r) => selection[String(r.id)])
    if (!chosen.length) {
      toast.warning('No chapters selected')
      return
    }
    setRetrying(true)
    requestNotifyPermission()
    try {
      const res = await regenerateBulk(
        chosen.map((r) => ({ id: r.id, series: r.series, title: r.title })),
      )
      toast.success(`Queued ${res.queued} of ${res.requested} retry job(s)`)
      setSelection({})
      void queryClient.invalidateQueries({ queryKey: qk.status })
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not queue retries')
    } finally {
      setRetrying(false)
    }
  }

  const columns = useMemo<ColumnDef<FailedChapter>[]>(
    () => [
      {
        id: 'select',
        size: 36,
        enableSorting: false,
        header: ({ table }) => (
          <Checkbox
            checked={table.getIsAllRowsSelected()}
            indeterminate={table.getIsSomeRowsSelected()}
            onChange={(on) => table.toggleAllRowsSelected(on)}
          />
        ),
        cell: ({ row }) => (
          <Checkbox checked={row.getIsSelected()} onChange={(on) => row.toggleSelected(on)} />
        ),
      },
      {
        accessorKey: 'series',
        header: 'Series',
        cell: ({ row }) => <span className="text-dim">{row.original.series}</span>,
      },
      {
        accessorKey: 'title',
        header: 'Chapter',
        sortingFn: naturalSort,
        cell: ({ row }) => <span className="text-text">{row.original.title}</span>,
      },
      {
        accessorKey: 'error',
        header: 'Error',
        cell: ({ row }) => (
          <span
            className="block max-w-[320px] truncate text-error/90"
            title={row.original.error}
          >
            {row.original.error}
          </span>
        ),
      },
      {
        accessorKey: 'retries',
        header: 'Retries',
        size: 70,
        meta: { align: 'center' },
        cell: ({ row }) => <span className="text-dim">{row.original.retries}</span>,
      },
      {
        accessorKey: 'updated_at',
        header: 'When',
        size: 130,
        cell: ({ row }) => <span className="text-dim">{fmtWhen(row.original.updated_at)}</span>,
      },
      {
        id: 'actions',
        size: 50,
        enableSorting: false,
        meta: { align: 'center' },
        header: '',
        cell: ({ row }) => (
          <IconButton
            title="Retry (regenerate)"
            onClick={() =>
              submitJob.mutate(() =>
                regenerateChapter(row.original.id, row.original.series, row.original.title),
              )
            }
          >
            <RotateCw size={14} />
          </IconButton>
        ),
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  )

  const title = seriesFilter ? `Failed Chapters — ${seriesFilter}` : 'Failed Chapters'

  return (
    <>
      <PageHeader title={title} titleColor="var(--color-error)" backTo="/" />
      <QueuePanel status={status} />

      <section className="flex w-full flex-col gap-1.5">
        <div className="flex w-full flex-wrap items-center justify-between gap-2">
          <span className="flex items-center gap-3">
            <Kicker>failed</Kicker>
            <Button
              variant="accent"
              disabled={retrying || selectedIds.length === 0}
              onClick={() => void retrySelected()}
            >
              {retrying ? 'Queueing…' : `Retry Selected (${selectedIds.length})`}
            </Button>
          </span>
          <SearchInput value={filter} onChange={setFilter} />
        </div>
        <DataTable
          columns={columns}
          data={rows}
          isLoading={isLoading}
          defaultSort={[{ id: 'updated_at', desc: true }]}
          pageSize={20}
          globalFilter={filter}
          tableId="failed"
          getRowId={(r) => String(r.id)}
          rowSelection={selection}
          onRowSelectionChange={setSelection}
          emptyState={<EmptyState>no failed chapters</EmptyState>}
        />
      </section>
    </>
  )
}
