import { useQuery } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { fetchAttemptStatus } from '../api/client'
import type { Attempt } from '../types'

export const POLLING_TIMEOUT_MS = 6 * 60 * 1000 // Part 2 worst case ~270s: transcription (120s) + signals (30s) + LLM (120s)
export const POLLING_INTERVAL_MS = 1500
export const POLLING_SLOW_INTERVAL_MS = 15 * 1000
const PROCESSING_STATUSES = ['processing', 'transcribing', 'scoring']

export interface PollingStart {
  key: number | null
  at: number
}

export interface PollingOptions<S extends string> {
  key?: number | null
  isInProgress?: (status: S) => boolean
}

/**
 * refetchInterval decision. The start is keyed to the polled id so one item cannot time
 * out the next, and a timed-out item keeps polling slowly so a late status still lands.
 */
export function nextPollingInterval<S extends string>(
  status: S | undefined,
  start: { current: PollingStart | null },
  setIsTimedOut: (timedOut: boolean) => void,
  {
    key = null,
    isInProgress = (value: S) => PROCESSING_STATUSES.includes(value),
  }: PollingOptions<S> = {},
): number | false {
  if (status && !isInProgress(status)) {
    start.current = null
    setIsTimedOut(false)
    return false
  }
  const now = Date.now()
  if (!start.current || start.current.key !== key) start.current = { key, at: now }
  if (now - start.current.at > POLLING_TIMEOUT_MS) {
    setIsTimedOut(true)
    return POLLING_SLOW_INTERVAL_MS
  }
  return POLLING_INTERVAL_MS
}

export function usePolling(attemptId: number | null): { data: Attempt | null; isTimedOut: boolean } {
  const startRef = useRef<PollingStart | null>(null)
  const [timedOutAttemptId, setTimedOutAttemptId] = useState<number | null>(null)

  const { data } = useQuery<Attempt>({
    queryKey: ['attempt', attemptId],
    queryFn: () => fetchAttemptStatus(attemptId!),
    enabled: attemptId !== null,
    refetchInterval: (query) =>
      nextPollingInterval(
        query.state.data?.status,
        startRef,
        (timedOut) => setTimedOutAttemptId(timedOut ? attemptId : null),
        { key: attemptId },
      ),
    refetchIntervalInBackground: true,
    staleTime: 0,
  })

  return { data: data ?? null, isTimedOut: attemptId !== null && timedOutAttemptId === attemptId }
}
