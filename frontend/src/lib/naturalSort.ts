/** Natural numeric ordering: "Chapter 2" sorts before "Chapter 10". */

import type { Row } from '@tanstack/react-table'

const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })

export const naturalCompare = (a: string, b: string) => collator.compare(a ?? '', b ?? '')

/** TanStack Table sortingFn for text columns with embedded numbers. */
export function naturalSort<T>(rowA: Row<T>, rowB: Row<T>, columnId: string): number {
  return collator.compare(
    String(rowA.getValue(columnId) ?? ''),
    String(rowB.getValue(columnId) ?? ''),
  )
}
