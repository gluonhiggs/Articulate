import {
  ATTEMPT_TIMEOUT_MESSAGE,
  attemptOutcome,
} from '../components/questions/utils'

describe('attemptOutcome', () => {
  it('stays pending while the attempt is still being processed', () => {
    for (const status of ['processing', 'transcribing', 'scoring']) {
      expect(attemptOutcome(status, false)).toEqual({ kind: 'pending' })
    }
  })

  it('stays pending when no status has arrived yet', () => {
    expect(attemptOutcome(undefined, false)).toEqual({ kind: 'pending' })
  })

  it('reports ready', () => {
    expect(attemptOutcome('ready', false)).toEqual({ kind: 'ready' })
  })

  it('explains a quota failure instead of blaming the API key', () => {
    const outcome = attemptOutcome('failed:quota', false)
    expect(outcome.kind).toBe('error')
    expect(outcome).toHaveProperty('message', expect.stringContaining('Daily quota'))
  })

  it('prefers the real failure over a timeout that fired while the tab was hidden', () => {
    expect(attemptOutcome('failed:quota', true)).toEqual({
      kind: 'error',
      message: expect.stringContaining('Daily quota'),
    })
  })

  it('prefers a finished attempt over a stale timeout', () => {
    expect(attemptOutcome('ready', true)).toEqual({ kind: 'ready' })
  })

  it('reports the timeout only while the attempt is still processing', () => {
    expect(attemptOutcome('scoring', true)).toEqual({ kind: 'error', message: ATTEMPT_TIMEOUT_MESSAGE })
    expect(attemptOutcome(undefined, true)).toEqual({ kind: 'error', message: ATTEMPT_TIMEOUT_MESSAGE })
  })

  it('falls back to a generic message for an unknown failure', () => {
    expect(attemptOutcome('failed', false)).toEqual({ kind: 'error', message: 'Scoring failed' })
  })
})
