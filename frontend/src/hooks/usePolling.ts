import { useQuery } from '@tanstack/react-query'
import { fetchAttemptStatus } from '../api/client'
import type { Attempt } from '../types'

export function usePolling(attemptId: number | null): Attempt | null {
  const { data } = useQuery<Attempt>({
    queryKey: ['attempt', attemptId],
    queryFn: () => fetchAttemptStatus(attemptId!),
    enabled: attemptId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'processing' || status === undefined) {
        return 1500
      }
      return false
    },
    staleTime: 0,
  })

  return data ?? null
}
