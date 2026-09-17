/**
 * Tests for the usePolling timeout logic.
 *
 * The hook polls /attempts/:id every POLLING_INTERVAL_MS while the attempt is processing.
 * After POLLING_TIMEOUT_MS, it stops polling and surfaces isTimedOut=true
 * to the caller so the UI can show an error.
 *
 * Rather than rendering the full hook with TanStack Query infrastructure,
 * we test the exported refetchInterval decision function the hook uses.
 */

import { nextPollingInterval, POLLING_INTERVAL_MS, POLLING_TIMEOUT_MS } from '../hooks/usePolling'

function makeIntervalDecision(
  startedAtRef: { current: number | null },
  setIsTimedOut: (v: boolean) => void,
) {
  return (status: string | undefined) => nextPollingInterval(status, startedAtRef, setIsTimedOut)
}

describe('usePolling interval logic', () => {
  it('keeps polling while processing within the timeout window', () => {
    const startedAtRef = { current: Date.now() }
    const setIsTimedOut = vi.fn()
    const decide = makeIntervalDecision(startedAtRef, setIsTimedOut)
    expect(decide('processing')).toBe(POLLING_INTERVAL_MS)
    expect(setIsTimedOut).not.toHaveBeenCalled()
  })

  it.each(['transcribing', 'scoring'])('keeps polling while status is %s', (status) => {
    const startedAtRef = { current: Date.now() }
    const setIsTimedOut = vi.fn()
    const decide = makeIntervalDecision(startedAtRef, setIsTimedOut)
    expect(decide(status)).toBe(POLLING_INTERVAL_MS)
    expect(setIsTimedOut).not.toHaveBeenCalled()
  })

  it('keeps polling when status is undefined (first poll, no data yet)', () => {
    const startedAtRef = { current: Date.now() }
    const setIsTimedOut = vi.fn()
    const decide = makeIntervalDecision(startedAtRef, setIsTimedOut)
    expect(decide(undefined)).toBe(POLLING_INTERVAL_MS)
  })

  it('records startedAt on the first processing call', () => {
    const startedAtRef: { current: number | null } = { current: null }
    const before = Date.now()
    const decide = makeIntervalDecision(startedAtRef, vi.fn())
    decide('processing')
    expect(startedAtRef.current).toBeGreaterThanOrEqual(before)
    expect(startedAtRef.current).toBeLessThanOrEqual(Date.now())
  })

  it('does NOT overwrite startedAt on subsequent processing calls', () => {
    const startedAtRef = { current: 1000 } // already set
    const decide = makeIntervalDecision(startedAtRef, vi.fn())
    decide('processing')
    expect(startedAtRef.current).toBe(1000)
  })

  it('sets isTimedOut=true and returns false after POLLING_TIMEOUT_MS of processing', () => {
    const startedAtRef = { current: Date.now() - POLLING_TIMEOUT_MS - 1 }
    const setIsTimedOut = vi.fn()
    const decide = makeIntervalDecision(startedAtRef, setIsTimedOut)
    expect(decide('processing')).toBe(false)
    expect(setIsTimedOut).toHaveBeenCalledWith(true)
  })

  it('returns false and clears state when status becomes ready', () => {
    const startedAtRef = { current: 99999 }
    const setIsTimedOut = vi.fn()
    const decide = makeIntervalDecision(startedAtRef, setIsTimedOut)
    expect(decide('ready')).toBe(false)
    expect(startedAtRef.current).toBeNull()
    expect(setIsTimedOut).toHaveBeenCalledWith(false)
  })

  it('returns false and clears state when status becomes failed', () => {
    const startedAtRef = { current: 99999 }
    const setIsTimedOut = vi.fn()
    const decide = makeIntervalDecision(startedAtRef, setIsTimedOut)
    expect(decide('failed')).toBe(false)
    expect(startedAtRef.current).toBeNull()
    expect(setIsTimedOut).toHaveBeenCalledWith(false)
  })

  it('does not time out just before POLLING_TIMEOUT_MS (must be strictly greater)', () => {
    // Use 100ms before the boundary so Date.now() advancing during the test
    // does not cross the timeout threshold (same semantic: not yet timed out).
    const startedAtRef = { current: Date.now() - POLLING_TIMEOUT_MS + 100 }
    const setIsTimedOut = vi.fn()
    const decide = makeIntervalDecision(startedAtRef, setIsTimedOut)
    expect(decide('processing')).toBe(POLLING_INTERVAL_MS)
    expect(setIsTimedOut).not.toHaveBeenCalledWith(true)
  })
})
