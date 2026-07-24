/** 1s ticker for the running job's elapsed time. */

import { useEffect, useState } from 'react'
import { elapsedSince } from '../lib/format'

export function useElapsed(startedAt: number | null): number {
  const [elapsed, setElapsed] = useState(() => (startedAt ? elapsedSince(startedAt) : 0))

  useEffect(() => {
    if (!startedAt) return
    setElapsed(elapsedSince(startedAt))
    const id = setInterval(() => setElapsed(elapsedSince(startedAt)), 1000)
    return () => clearInterval(id)
  }, [startedAt])

  return startedAt ? elapsed : 0
}
