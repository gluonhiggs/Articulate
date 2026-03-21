import type { RecordingStatus } from '../../store/recordingStore'
import { CountdownTimer } from './CountdownTimer'

interface RecordingBarProps {
  status: RecordingStatus
  elapsed: number
  max: number
  onStart: () => void
  onStop: () => void
  onRetry?: () => void
  errorMessage?: string | null
  backendStatus?: string | null
}

const BACKEND_STEP_LABELS: Record<string, string> = {
  transcribing:             'Scoring...',
  scoring:                  'Scoring...',
  'failed:transcription':   'Could not transcribe audio',
  'failed:empty_audio':     'Audio was too quiet or silent',
  'failed:scoring':         'AI scoring unavailable (is Ollama running?)',
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

function Spinner() {
  return (
    <svg
      className="animate-spin h-5 w-5 text-accent"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  )
}

export function RecordingBar({
  status,
  elapsed,
  max,
  onStart,
  onStop,
  onRetry,
  errorMessage,
  backendStatus,
}: RecordingBarProps) {
  return (
    <div className="sticky bottom-0 left-0 right-0 bg-sidebar/95 backdrop-blur border-t border-cardBorder px-6 py-4 z-10">
      <div className="max-w-3xl mx-auto flex items-center justify-between gap-4">
        {status === 'idle' && (
          <>
            <p className="text-textSecondary text-sm">Ready to practice?</p>
            <button
              onClick={onStart}
              className="flex items-center gap-2 px-6 py-2.5 rounded-lg bg-gradient-to-r from-cyan-500 to-purple-600 text-white font-semibold text-sm hover:opacity-90 transition-opacity focus:outline-none focus:ring-2 focus:ring-accent/50"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-4 w-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
                />
              </svg>
              Record
            </button>
          </>
        )}

        {status === 'preparing' && (
          <>
            <div className="flex items-center gap-3">
              <CountdownTimer seconds={max - elapsed} maxSeconds={max} />
              <div>
                <p className="text-textPrimary text-sm font-medium">Preparing...</p>
                <p className="text-textSecondary text-xs">
                  Recording starts in {Math.max(0, max - elapsed)}s
                </p>
              </div>
            </div>
            <button
              onClick={onStop}
              className="px-4 py-2 rounded-lg border border-cardBorder text-textSecondary text-sm hover:text-textPrimary hover:border-textSecondary transition-colors"
            >
              Skip
            </button>
          </>
        )}

        {status === 'recording' && (
          <>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-red-500 pulse-record" />
                <span className="text-red-400 text-sm font-medium">Recording</span>
              </div>
              <span className="text-textSecondary text-sm">
                {formatTime(elapsed)} / {formatTime(max)}
              </span>
            </div>
            <div className="flex-1 mx-4 bg-background rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-red-500 h-full rounded-full transition-all duration-1000 ease-linear"
                style={{ width: `${Math.min(100, (elapsed / max) * 100)}%` }}
              />
            </div>
            <button
              onClick={onStop}
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-red-600 hover:bg-red-700 text-white font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-red-500/50"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-4 w-4"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <rect x="6" y="6" width="12" height="12" rx="1" />
              </svg>
              Stop
            </button>
          </>
        )}

        {(status === 'uploading' || status === 'polling') && (
          <div className="flex items-center gap-3 w-full">
            <Spinner />
            <p className="text-textSecondary text-sm">
              {status === 'uploading'
                ? 'Uploading...'
                : (BACKEND_STEP_LABELS[backendStatus ?? ''] ?? 'Scoring...')}
            </p>
          </div>
        )}

        {status === 'done' && (
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5 text-green-400"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <p className="text-green-400 text-sm font-medium">Done! Results updated.</p>
            </div>
            <button
              onClick={onStart}
              className="flex items-center gap-2 px-5 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-purple-600 text-white font-semibold text-sm hover:opacity-90 transition-opacity"
            >
              Record again
            </button>
          </div>
        )}

        {status === 'error' && (
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5 text-red-400"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <p className="text-red-400 text-sm">{errorMessage ?? 'An error occurred'}</p>
            </div>
            <button
              onClick={onRetry}
              className="px-4 py-2 rounded-lg border border-red-500/50 text-red-400 text-sm hover:bg-red-500/10 transition-colors"
            >
              Retry
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
