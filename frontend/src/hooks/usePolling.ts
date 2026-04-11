import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { fetchAttemptStatus } from '../api/client'
import type { Attempt } from '../types'

const POLLING_TIMEOUT_MS = 6 * 60 * 1000 // 6 minutes - Part 2: transcription (120s) + signals (30s) + LLM (120s) = ~270s max

export function usePolling(attemptId: number | null): { data: Attempt | null; isTimedOut: boolean } {
  const startedAtRef = useRef<number | null>(null)
  const [isTimedOut, setIsTimedOut] = useState(false)

  // Reset timer and timeout flag whenever a new attempt starts.
  // Without this, a timed-out attempt leaves startedAtRef holding a stale
  // timestamp, causing the very next attempt's polling to time out immediately.
  useEffect(() => {
    startedAtRef.current = null
    setIsTimedOut(false)
  }, [attemptId])

  const { data } = useQuery<Attempt>({
    queryKey: ['attempt', attemptId],
    queryFn: () => fetchAttemptStatus(attemptId!),
    enabled: attemptId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      const PROCESSING_STATUSES = ['processing', 'transcribing', 'scoring']
      if (!status || PROCESSING_STATUSES.includes(status)) {
        if (!startedAtRef.current) startedAtRef.current = Date.now()
        if (Date.now() - startedAtRef.current > POLLING_TIMEOUT_MS) {
          setIsTimedOut(true)
          return false
        }
        return 1500
      }
      startedAtRef.current = null
      setIsTimedOut(false)
      return false
    },
    staleTime: 0,
  })

  return { data: data ?? null, isTimedOut }
}
