/**
 * Namespaced console logging, formatted like the backend's
 * "%(asctime)s [%(levelname)s] %(name)s - %(message)s".
 *
 * info, warn and error always print, matching the backend's logging level. debug adds
 * per-request noise and needs localStorage.setItem('articulate:debug', '1') in DevTools,
 * or the Vite dev server, which turns it on for everyone.
 */

type Level = 'debug' | 'info' | 'warn' | 'error'

const STORAGE_KEY = 'articulate:debug'

function storedFlag(): boolean {
  try {
    return globalThis.localStorage?.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

let verbose = import.meta.env.DEV || storedFlag()  // verbose adds the debug level

export function setVerboseLogging(on: boolean): void {
  verbose = on
  try {
    if (on) globalThis.localStorage?.setItem(STORAGE_KEY, '1')
    else globalThis.localStorage?.removeItem(STORAGE_KEY)
  } catch {
    // Unavailable storage still leaves the in-memory flag for this session.
  }
}

export function isVerboseLogging(): boolean {
  return verbose
}

/** Error-like values flattened into something console-readable. */
export function errorData(err: unknown): Record<string, unknown> {
  if (err instanceof Error) return { name: err.name, message: err.message, stack: err.stack }
  return { value: err }
}

function emit(level: Level, namespace: string, message: string, data?: unknown): void {
  if (level === 'debug' && !verbose) return
  const stamp = new Date().toISOString().slice(11, 23)
  const line = `${stamp} [${level.toUpperCase()}] ${namespace} - ${message}`
  const write = level === 'debug' ? console.debug : level === 'info' ? console.info : level === 'warn' ? console.warn : console.error
  if (data === undefined) write(line)
  else write(line, data)
}

export interface Logger {
  debug: (message: string, data?: unknown) => void
  info: (message: string, data?: unknown) => void
  warn: (message: string, data?: unknown) => void
  error: (message: string, data?: unknown) => void
}

export function createLogger(namespace: string): Logger {
  return {
    debug: (message, data) => emit('debug', namespace, message, data),
    info: (message, data) => emit('info', namespace, message, data),
    warn: (message, data) => emit('warn', namespace, message, data),
    error: (message, data) => emit('error', namespace, message, data),
  }
}
