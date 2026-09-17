import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { fetchAttemptStatus } from '../api/client'
import type { Attempt } from '../types'

export const POLLING_TIMEOUT_MS = 6 * 60 * 1000 // Part 2 worst case ~270s: transcription (120s) + signals (30s) + LLM (120s)
export const POLLING_INTERVAL_MS = 1500
const PROCESSING_STATUSES = ['processing', 'transcribing', 'scoring']

/**
 * refetchInterval decision: keep polling while the attempt is still being processed
 * (or no status has arrived yet), and give up with isTimedOut=true after POLLING_TIMEOUT_MS.
 */
export function nextPollingInterval(
  status: string | undefined,
  startedAtRef: { current: number | null },
  setIsTimedOut: (timedOut: boolean) => void,
): number | false {
  if (!status || PROCESSING_STATUSES.includes(status)) {
    if (!startedAtRef.current) startedAtRef.current = Date.now()
    if (Date.now() - startedAtRef.current > POLLING_TIMEOUT_MS) {
      setIsTimedOut(true)
      return false
    }
    return POLLING_INTERVAL_MS
  }
  startedAtRef.current = null
  setIsTimedOut(false)
  return false
}

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
    refetchInterval: (query) => nextPollingInterval(query.state.data?.status, startedAtRef, setIsTimedOut),
    staleTime: 0,
  })

  return { data: data ?? null, isTimedOut }
}
