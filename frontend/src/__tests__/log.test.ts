import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createLogger, errorData, isVerboseLogging, setVerboseLogging } from '../lib/log'

const log = createLogger('test')

describe('log', () => {
  beforeEach(() => {
    vi.spyOn(console, 'debug').mockImplementation(() => {})
    vi.spyOn(console, 'info').mockImplementation(() => {})
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('keeps only debug quiet when verbose logging is off', () => {
    setVerboseLogging(false)
    log.debug('hidden')
    expect(console.debug).not.toHaveBeenCalled()
  })

  it('reports info, warnings and errors by default, like the backend', () => {
    setVerboseLogging(false)
    log.info('what happened')
    log.warn('watch out')
    log.error('broken')
    expect(console.info).toHaveBeenCalledTimes(1)
    expect(console.warn).toHaveBeenCalledTimes(1)
    expect(console.error).toHaveBeenCalledTimes(1)
  })

  it('adds debug once verbose logging is on', () => {
    setVerboseLogging(true)
    expect(isVerboseLogging()).toBe(true)
    log.debug('now visible')
    expect(console.debug).toHaveBeenCalledTimes(1)
  })

  it('names the level and the namespace in the line', () => {
    setVerboseLogging(true)
    log.info('upload ok', { answerId: 4 })
    const [line, data] = vi.mocked(console.info).mock.calls[0]
    expect(line).toContain('[INFO] test - upload ok')
    expect(data).toEqual({ answerId: 4 })
  })

  it('works where localStorage is unavailable', () => {
    // vitest runs with environment: 'node', so there is no localStorage here at all.
    expect(() => setVerboseLogging(true)).not.toThrow()
    expect(() => log.warn('still fine')).not.toThrow()
  })

  it('flattens errors into something console-readable', () => {
    const flattened = errorData(new Error('boom'))
    expect(flattened).toMatchObject({ name: 'Error', message: 'boom' })
    expect(errorData('plain string')).toEqual({ value: 'plain string' })
  })
})
