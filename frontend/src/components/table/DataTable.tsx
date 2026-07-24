import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type OnChangeFn,
  type RowSelectionState,
  type SortingState,
} from '@tanstack/react-table'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Skeleton } from '../ui/Skeleton'
import { TablePagination } from './TablePagination'

interface Props<T> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  columns: ColumnDef<T, any>[]
  data: T[]
  isLoading?: boolean
  defaultSort?: SortingState
  pageSize?: number
  globalFilter?: string
  getRowId: (row: T) => string
  onRowClick?: (row: T) => void
  emptyState?: ReactNode
  rowSelection?: RowSelectionState
  onRowSelectionChange?: OnChangeFn<RowSelectionState>
}

export function DataTable<T>({
  columns,
  data,
  isLoading,
  defaultSort = [],
  pageSize = 20,
  globalFilter,
  getRowId,
  onRowClick,
  emptyState,
  rowSelection,
  onRowSelectionChange,
}: Props<T>) {
  const [sorting, setSorting] = useState<SortingState>(defaultSort)

  const table = useReactTable({
    data,
    columns,
    state: { sorting, globalFilter, rowSelection: rowSelection ?? {} },
    onSortingChange: setSorting,
    onRowSelectionChange,
    enableRowSelection: !!onRowSelectionChange,
    getRowId,
    globalFilterFn: 'includesString',
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize } },
    autoResetPageIndex: false,
  })

  const rows = table.getRowModel().rows

  return (
    <div className="w-full rounded-sm border border-border bg-surface">
      <div className="w-full overflow-x-auto">
        <table className="w-full border-collapse text-[13px]">
          <thead className="sticky top-0 z-10 bg-surface">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} className="border-b border-border">
                {hg.headers.map((header) => {
                  const sortable = header.column.getCanSort()
                  const dir = header.column.getIsSorted()
                  return (
                    <th
                      key={header.id}
                      onClick={sortable ? header.column.getToggleSortingHandler() : undefined}
                      className={`px-3 py-2 text-[11px] font-medium tracking-[0.08em]
                        text-dim uppercase select-none
                        ${sortable ? 'cursor-pointer hover:text-text' : ''}
                        ${(header.column.columnDef.meta as ColMeta)?.align === 'center' ? 'text-center' : 'text-left'}`}
                      style={{ width: header.column.columnDef.size }}
                    >
                      <span className="inline-flex items-center gap-1">
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {dir === 'asc' && <ChevronUp size={12} className="text-accent" />}
                        {dir === 'desc' && <ChevronDown size={12} className="text-accent" />}
                      </span>
                    </th>
                  )
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {isLoading && data.length === 0
              ? Array.from({ length: 5 }, (_, i) => (
                  <tr key={i} className="border-b border-border/50">
                    {columns.map((_, ci) => (
                      <td key={ci} className="px-3 py-2">
                        <Skeleton className="h-4 w-full" />
                      </td>
                    ))}
                  </tr>
                ))
              : rows.map((row) => (
                  <tr
                    key={row.id}
                    onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                    className={`border-b border-border/50 transition-colors duration-100
                      last:border-b-0 hover:bg-accent/5
                      ${onRowClick ? 'cursor-pointer' : ''}
                      ${row.getIsSelected() ? 'bg-accent/5' : ''}`}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td
                        key={cell.id}
                        className={`px-3 py-1.5 ${(cell.column.columnDef.meta as ColMeta)?.align === 'center' ? 'text-center' : ''}`}
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
          </tbody>
        </table>
        {!isLoading && rows.length === 0 && emptyState}
      </div>
      <TablePagination table={table} />
    </div>
  )
}

interface ColMeta {
  align?: 'left' | 'center'
}
