export const ATTEMPT_PROCESSING_STATUSES = ['processing', 'transcribing', 'scoring'] as const
export const ATTEMPT_FAILED_STATUSES = [
  'failed',
  'failed:transcription',
  'failed:empty_audio',
  'failed:scoring',
  'failed:quota',
] as const
export const ATTEMPT_STATUSES = [...ATTEMPT_PROCESSING_STATUSES, 'ready', ...ATTEMPT_FAILED_STATUSES] as const

export type AttemptProcessingStatus = (typeof ATTEMPT_PROCESSING_STATUSES)[number]
export type AttemptFailedStatus = (typeof ATTEMPT_FAILED_STATUSES)[number]
export type AttemptStatus = (typeof ATTEMPT_STATUSES)[number]

const PROCESSING = new Set<string>(ATTEMPT_PROCESSING_STATUSES)

export function isAttemptProcessing(status: string): boolean {
  return PROCESSING.has(status)
}

/** Prefix match, so a status added on the backend still reads as a failure here. */
export function isAttemptFailed(status: string): boolean {
  return status === 'failed' || status.startsWith('failed:')
}

export function isAttemptReady(status: string): boolean {
  return status === 'ready'
}
