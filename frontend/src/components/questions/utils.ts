import {
  isAttemptFailed,
  isAttemptProcessing,
  isAttemptReady,
  type AttemptFailedStatus,
  type AttemptProcessingStatus,
} from '../../types/attemptStatus'

export function partMaxSeconds(part: string): number {
  return part === '2' ? 120 : part === '3' ? 60 : 45
}

export function partLabel(part: string): string {
  return part === '1' ? 'Part 1' : part === '2' ? 'Part 2' : part === '3' ? 'Part 3' : 'Custom'
}

export function partRoute(part: string, id?: number): string {
  const base = part === '1' ? '/practice/part1' : part === '2' ? '/practice/part2' : part === '3' ? '/practice/part3' : '/'
  return id !== undefined ? `${base}/questions/${id}` : base
}

export function scoreColor(s: number) {
  if (s >= 7) return { ring: 'border-teal-400', text: 'text-teal-400', glow: 'glow-circle' }
  if (s >= 6) return { ring: 'border-purple-400', text: 'text-purple-400', glow: '' }
  if (s >= 5) return { ring: 'border-yellow-400', text: 'text-yellow-400', glow: '' }
  return { ring: 'border-red-400', text: 'text-red-400', glow: '' }
}

export function tagClass(s: number) {
  if (s >= 7) return 'tag-high'
  if (s >= 5) return 'tag-mid'
  return 'tag-low'
}

export function cleanWord(s: string): string {
  return s.replace(/[.,!?;:'"()\-]/g, '').toLowerCase()
}

export const ATTEMPT_ERROR_MESSAGES: Record<AttemptFailedStatus, string> = {
  failed: 'Scoring failed',
  'failed:transcription': 'Could not transcribe audio',
  'failed:empty_audio': 'Audio was too quiet or silent',
  'failed:scoring': 'AI scoring unavailable - check your LLM API key',
  'failed:quota':
    'Daily quota for the scoring model is used up (it resets at midnight US Pacific). Your recording and transcript are saved - switch the scoring model in the sidebar to keep practising.',
}

export const ATTEMPT_TIMEOUT_MESSAGE = 'Scoring timed out - the server is taking too long. Please try again.'

export const ATTEMPT_PROCESSING_LABELS: Record<AttemptProcessingStatus, string> = {
  processing: 'Processing...',
  transcribing: 'Transcribing...',
  scoring: 'Scoring...',
}

export const ATTEMPT_FAILURE_LABELS: Record<AttemptFailedStatus, string> = {
  failed: 'Processing failed - please try recording again.',
  'failed:transcription': 'Transcription failed',
  'failed:empty_audio': 'No speech detected',
  'failed:scoring': 'Scoring failed',
  'failed:quota': 'Scoring quota reached - transcript saved',
}

export function attemptProcessingLabel(status: string): string {
  return ATTEMPT_PROCESSING_LABELS[status as AttemptProcessingStatus] ?? 'Processing...'
}

export function attemptFailureLabel(status: string): string {
  return ATTEMPT_FAILURE_LABELS[status as AttemptFailedStatus] ?? ATTEMPT_FAILURE_LABELS.failed
}

export function attemptErrorMessage(status: string): string {
  return ATTEMPT_ERROR_MESSAGES[status as AttemptFailedStatus] ?? ATTEMPT_ERROR_MESSAGES.failed
}

export function attemptStepLabel(status: string | null | undefined): string {
  if (!status) return 'Scoring...'
  if (isAttemptFailed(status)) return attemptFailureLabel(status)
  return attemptProcessingLabel(status)
}

export type AttemptOutcome = { kind: 'pending' } | { kind: 'ready' } | { kind: 'error'; message: string }

export function attemptOutcome(status: string | undefined, timedOut: boolean): AttemptOutcome {
  if (status && isAttemptReady(status)) return { kind: 'ready' }
  if (status && !isAttemptProcessing(status)) return { kind: 'error', message: attemptErrorMessage(status) }
  if (timedOut) return { kind: 'error', message: ATTEMPT_TIMEOUT_MESSAGE }
  return { kind: 'pending' }
}
