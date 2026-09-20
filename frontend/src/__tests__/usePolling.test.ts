/**
 * Tests for the usePolling timeout logic.
 *
 * The hook polls /attempts/:id every POLLING_INTERVAL_MS while the attempt is processing.
 * After POLLING_TIMEOUT_MS it surfaces isTimedOut=true and falls back to
 * POLLING_SLOW_INTERVAL_MS, so a status written later still reaches the UI.
 *
 * Rather than rendering the full hook with TanStack Query infrastructure,
 * we test the exported refetchInterval decision function the hook uses.
 */

import {
  nextPollingInterval,
  POLLING_INTERVAL_MS,
  POLLING_SLOW_INTERVAL_MS,
  POLLING_TIMEOUT_MS,
  type PollingStart,
} from '../hooks/usePolling'

function makeIntervalDecision(
  startRef: { current: PollingStart | null },
  setIsTimedOut: (v: boolean) => void,
  key: number | null = 1,
) {
  return (status: string | undefined) => nextPollingInterval(status, startRef, setIsTimedOut, { key })
}

function startedAt(at: number, key: number | null = 1): { current: PollingStart | null } {
  return { current: { key, at } }
}

describe('usePolling interval logic', () => {
  it('keeps polling while processing within the timeout window', () => {
    const setIsTimedOut = vi.fn()
    const decide = makeIntervalDecision(startedAt(Date.now()), setIsTimedOut)
    expect(decide('processing')).toBe(POLLING_INTERVAL_MS)
    expect(setIsTimedOut).not.toHaveBeenCalled()
  })

  it.each(['transcribing', 'scoring'])('keeps polling while status is %s', (status) => {
    const setIsTimedOut = vi.fn()
    const decide = makeIntervalDecision(startedAt(Date.now()), setIsTimedOut)
    expect(decide(status)).toBe(POLLING_INTERVAL_MS)
    expect(setIsTimedOut).not.toHaveBeenCalled()
  })

  it('keeps polling when status is undefined (first poll, no data yet)', () => {
    const decide = makeIntervalDecision(startedAt(Date.now()), vi.fn())
    expect(decide(undefined)).toBe(POLLING_INTERVAL_MS)
  })

  it('records the start on the first processing call', () => {
    const startRef: { current: PollingStart | null } = { current: null }
    const before = Date.now()
    makeIntervalDecision(startRef, vi.fn(), 7)('processing')
    expect(startRef.current?.key).toBe(7)
    expect(startRef.current?.at).toBeGreaterThanOrEqual(before)
    expect(startRef.current?.at).toBeLessThanOrEqual(Date.now())
  })

  it('does NOT overwrite the start on subsequent processing calls', () => {
    const at = Date.now() - 5_000 // already set, still inside the timeout window
    const startRef = startedAt(at)
    expect(makeIntervalDecision(startRef, vi.fn())('processing')).toBe(POLLING_INTERVAL_MS)
    expect(startRef.current?.at).toBe(at)
  })

  it('restarts the window for a new attempt instead of inheriting the previous one', () => {
    const startRef = startedAt(Date.now() - POLLING_TIMEOUT_MS - 1, 1)
    const setIsTimedOut = vi.fn()
    expect(makeIntervalDecision(startRef, setIsTimedOut, 2)('scoring')).toBe(POLLING_INTERVAL_MS)
    expect(startRef.current?.key).toBe(2)
    expect(setIsTimedOut).not.toHaveBeenCalled()
  })

  it('keeps polling slowly after POLLING_TIMEOUT_MS so a late status still arrives', () => {
    const setIsTimedOut = vi.fn()
    const decide = makeIntervalDecision(startedAt(Date.now() - POLLING_TIMEOUT_MS - 1), setIsTimedOut)
    expect(decide('processing')).toBe(POLLING_SLOW_INTERVAL_MS)
    expect(setIsTimedOut).toHaveBeenCalledWith(true)
  })

  it('clears the timeout when a status finally arrives after the timeout', () => {
    const startRef = startedAt(Date.now() - POLLING_TIMEOUT_MS - 1)
    const setIsTimedOut = vi.fn()
    const decide = makeIntervalDecision(startRef, setIsTimedOut)
    expect(decide('failed:quota')).toBe(false)
    expect(startRef.current).toBeNull()
    expect(setIsTimedOut).toHaveBeenCalledWith(false)
  })

  it('returns false and clears state when status becomes ready', () => {
    const startRef = startedAt(99999)
    const setIsTimedOut = vi.fn()
    expect(makeIntervalDecision(startRef, setIsTimedOut)('ready')).toBe(false)
    expect(startRef.current).toBeNull()
    expect(setIsTimedOut).toHaveBeenCalledWith(false)
  })

  it.each(['failed', 'failed:transcription', 'failed:empty_audio', 'failed:scoring', 'failed:quota'])(
    'returns false and clears state when status becomes %s',
    (status) => {
      const startRef = startedAt(99999)
      const setIsTimedOut = vi.fn()
      expect(makeIntervalDecision(startRef, setIsTimedOut)(status)).toBe(false)
      expect(startRef.current).toBeNull()
      expect(setIsTimedOut).toHaveBeenCalledWith(false)
    },
  )

  describe('timeout boundary (strictly greater than POLLING_TIMEOUT_MS)', () => {
    const START = 1_700_000_000_000

    beforeEach(() => {
      vi.useFakeTimers()
    })

    afterEach(() => {
      vi.useRealTimers()
    })

    it('keeps polling at exactly POLLING_TIMEOUT_MS', () => {
      vi.setSystemTime(START + POLLING_TIMEOUT_MS)
      const setIsTimedOut = vi.fn()
      expect(makeIntervalDecision(startedAt(START), setIsTimedOut)('processing')).toBe(POLLING_INTERVAL_MS)
      expect(setIsTimedOut).not.toHaveBeenCalled()
    })

    it('times out 1ms after POLLING_TIMEOUT_MS', () => {
      vi.setSystemTime(START + POLLING_TIMEOUT_MS + 1)
      const setIsTimedOut = vi.fn()
      expect(makeIntervalDecision(startedAt(START), setIsTimedOut)('processing')).toBe(POLLING_SLOW_INTERVAL_MS)
      expect(setIsTimedOut).toHaveBeenCalledWith(true)
    })
  })
})
