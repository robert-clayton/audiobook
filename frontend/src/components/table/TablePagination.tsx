import type { Table } from '@tanstack/react-table'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { IconButton } from '../ui/IconButton'

const PAGE_SIZES = [10, 20, 50, 100]

export function TablePagination<T>({ table }: { table: Table<T> }) {
  const pageCount = table.getPageCount()
  const { pageIndex, pageSize } = table.getState().pagination
  const total = table.getFilteredRowModel().rows.length

  // Hide the footer only when everything fits at the smallest size anyway.
  if (pageCount <= 1 && total <= PAGE_SIZES[0]) return null

  return (
    <div className="flex w-full flex-wrap items-center justify-end gap-x-3 gap-y-1 border-t border-border px-3 py-1.5 text-[11px] text-dim">
      <label className="flex cursor-pointer items-center gap-1.5">
        rows
        <select
          value={pageSize}
          onChange={(e) => table.setPageSize(Number(e.target.value))}
          className="cursor-pointer rounded-sm border border-border bg-bg px-1 py-0.5
            text-[11px] text-text hover:border-border-strong focus:border-accent
            focus:outline-none"
        >
          {PAGE_SIZES.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </label>
      <span>
        {total} rows · page {Math.min(pageIndex + 1, pageCount)}/{Math.max(pageCount, 1)}
      </span>
      <span className="flex items-center">
        <IconButton
          title="Previous page"
          disabled={!table.getCanPreviousPage()}
          onClick={() => table.previousPage()}
        >
          <ChevronLeft size={14} />
        </IconButton>
        <IconButton
          title="Next page"
          disabled={!table.getCanNextPage()}
          onClick={() => table.nextPage()}
        >
          <ChevronRight size={14} />
        </IconButton>
      </span>
    </div>
  )
}
