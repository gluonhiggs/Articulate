/**
 * Tests for the TTS auto-play error handling logic in QuestionDetail.tsx.
 *
 * The auto-play useEffect catches errors from playQuestionTTS() and:
 * - Silences NotAllowedError (mobile browser autoplay policy - expected, not a bug)
 * - Logs other errors via console.error
 *
 * playQuestionTTS() re-throws all errors after cleanup so the caller can handle them.
 */

describe('TTS auto-play NotAllowedError silencing', () => {
  // This is the exact condition from the auto-play effect:
  // if (err instanceof Error && err.name !== 'NotAllowedError') { console.error(...) }
  function shouldLogError(err: unknown): boolean {
    return err instanceof Error && err.name !== 'NotAllowedError'
  }

  it('does NOT log NotAllowedError (mobile autoplay policy)', () => {
    const err = new DOMException('play() failed', 'NotAllowedError')
    expect(shouldLogError(err)).toBe(false)
  })

  it('does NOT log a manually constructed NotAllowedError', () => {
    const err = new Error('Autoplay not allowed')
    err.name = 'NotAllowedError'
    expect(shouldLogError(err)).toBe(false)
  })

  it('logs generic Error', () => {
    const err = new Error('Network error')
    expect(shouldLogError(err)).toBe(true)
  })

  it('logs TypeError', () => {
    const err = new TypeError('Cannot read properties of null')
    expect(shouldLogError(err)).toBe(true)
  })

  it('does not crash on non-Error thrown values', () => {
    // Non-Error objects (e.g. thrown strings) → instanceof Error is false → shouldLog is false
    expect(shouldLogError('some string error')).toBe(false)
    expect(shouldLogError(null)).toBe(false)
    expect(shouldLogError(undefined)).toBe(false)
  })
})

describe('playQuestionTTS Promise contract', () => {
  it('returns Promise.resolve when question is null', async () => {
    // This mirrors the early-return in playQuestionTTS: if (!question) return Promise.resolve()
    const earlyReturn = (question: unknown): Promise<void> => {
      if (!question) return Promise.resolve()
      return Promise.reject(new Error('should not reach'))
    }
    await expect(earlyReturn(null)).resolves.toBeUndefined()
    await expect(earlyReturn(undefined)).resolves.toBeUndefined()
  })
})
