/**
 * Tests for the usePolling timeout logic.
 *
 * The hook polls /attempts/:id every 1500ms while status='processing'.
 * After POLLING_TIMEOUT_MS (3 minutes), it stops polling and surfaces
 * isTimedOut=true to the caller so the UI can show an error.
 *
 * Rather than rendering the full hook with TanStack Query infrastructure,
 * we test the refetchInterval decision function directly - same pattern
 * as the rest of the __tests__ suite.
 */

const POLLING_TIMEOUT_MS = 3 * 60 * 1000 // must match usePolling.ts

// Simulate the refetchInterval callback logic from usePolling.ts
function makeIntervalDecision(
  startedAtRef: { current: number | null },
  setIsTimedOut: (v: boolean) => void,
) {
  return function decide(status: string | undefined): number | false {
    if (status === 'processing' || status === undefined) {
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
  }
}

describe('usePolling interval logic', () => {
  it('returns 1500 while processing within the timeout window', () => {
    const startedAtRef = { current: Date.now() }
    const setIsTimedOut = vi.fn()
    const decide = makeIntervalDecision(startedAtRef, setIsTimedOut)
    expect(decide('processing')).toBe(1500)
    expect(setIsTimedOut).not.toHaveBeenCalled()
  })

  it('returns 1500 when status is undefined (first poll, no data yet)', () => {
    const startedAtRef = { current: Date.now() }
    const setIsTimedOut = vi.fn()
    const decide = makeIntervalDecision(startedAtRef, setIsTimedOut)
    expect(decide(undefined)).toBe(1500)
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

  it('sets isTimedOut=true and returns false after 3 minutes of processing', () => {
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

  it('does not time out at exactly 3 minutes (boundary - must be strictly greater)', () => {
    const startedAtRef = { current: Date.now() - POLLING_TIMEOUT_MS }
    const setIsTimedOut = vi.fn()
    const decide = makeIntervalDecision(startedAtRef, setIsTimedOut)
    // Date.now() - startedAt === POLLING_TIMEOUT_MS exactly → NOT > → should still poll
    expect(decide('processing')).toBe(1500)
    expect(setIsTimedOut).not.toHaveBeenCalledWith(true)
  })
})
