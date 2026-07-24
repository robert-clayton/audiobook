/** Natural numeric ordering: "Chapter 2" sorts before "Chapter 10". */

import type { Row, SortingFn } from '@tanstack/react-table'

const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })

export const naturalCompare = (a: string, b: string) => collator.compare(a ?? '', b ?? '')

/** TanStack Table sortingFn for text columns with embedded numbers. */
export const naturalSort: SortingFn<unknown> = (
  rowA: Row<unknown>,
  rowB: Row<unknown>,
  columnId: string,
) => collator.compare(String(rowA.getValue(columnId) ?? ''), String(rowB.getValue(columnId) ?? ''))
