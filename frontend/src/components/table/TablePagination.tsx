import type { Table } from '@tanstack/react-table'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { IconButton } from '../ui/IconButton'

export function TablePagination<T>({ table }: { table: Table<T> }) {
  const pageCount = table.getPageCount()
  if (pageCount <= 1) return null
  const { pageIndex } = table.getState().pagination
  const total = table.getFilteredRowModel().rows.length

  return (
    <div className="flex w-full items-center justify-end gap-2 border-t border-border px-3 py-1.5 text-[11px] text-dim">
      <span>
        {total} rows · page {pageIndex + 1}/{pageCount}
      </span>
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
    </div>
  )
}
