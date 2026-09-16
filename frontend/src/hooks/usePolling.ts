import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { fetchAttemptStatus } from '../api/client'
import type { Attempt } from '../types'

const POLLING_TIMEOUT_MS = 6 * 60 * 1000 // Part 2 worst case ~270s: transcription (120s) + signals (30s) + LLM (120s)

export function usePolling(attemptId: number | null): { data: Attempt | null; isTimedOut: boolean } {
  const startedAtRef = useRef<number | null>(null)
  const [isTimedOut, setIsTimedOut] = useState(false)

  // Reset on every new attempt: otherwise a timed-out attempt leaves a stale
  // startedAtRef and the next attempt's polling times out immediately.
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
