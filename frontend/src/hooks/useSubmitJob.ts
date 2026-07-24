/** Job submission with queued / already-queued toasts. */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { ApiError } from '../api/client'
import type { SubmitResponse } from '../api/types'
import { qk } from '../lib/queryKeys'
import { requestNotifyPermission } from './useStatusPoll'

export function useSubmitJob() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (submit: () => Promise<SubmitResponse>) => {
      requestNotifyPermission()
      return submit()
    },
    onSuccess: (res) => {
      if (res.created) toast.success(`Queued: ${res.job.label}`)
      else toast.info(`Already queued: ${res.job.label}`)
      void queryClient.invalidateQueries({ queryKey: qk.status })
    },
    onError: (err) => {
      toast.error(err instanceof ApiError ? err.message : 'Request failed')
    },
  })
}
