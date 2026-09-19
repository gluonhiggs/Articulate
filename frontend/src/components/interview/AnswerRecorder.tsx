import { CountdownTimer } from '../recording/CountdownTimer'
import { outlineButtonClass } from './ui'
import { formatDuration } from './utils'

export type RecorderState = 'idle' | 'recording' | 'uploading'

export function AnswerRecorder({
  state,
  elapsed,
  maxSeconds,
  error,
  onStart,
  onStop,
  onRetryUpload,
}: {
  state: RecorderState
  elapsed: number
  maxSeconds: number
  error: string | null
  onStart: () => void
  onStop: () => void
  onRetryUpload?: () => void
}) {
  if (state === 'recording') {
    return (
      <div className="bg-card border border-red-500/30 rounded-xl p-5 flex items-center gap-4">
        <CountdownTimer seconds={Math.max(0, maxSeconds - elapsed)} maxSeconds={maxSeconds} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-red-500 pulse-record" />
            <span className="text-red-400 text-sm font-medium">Recording</span>
            <span className="text-textSecondary text-sm">
              {formatDuration(elapsed)} / {formatDuration(maxSeconds)}
            </span>
          </div>
          <div className="mt-2 bg-background rounded-full h-1.5 overflow-hidden">
            <div
              className="bg-red-500 h-full rounded-full transition-all duration-1000 ease-linear"
              style={{ width: `${Math.min(100, (elapsed / maxSeconds) * 100)}%` }}
            />
          </div>
        </div>
        <button
          onClick={onStop}
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-red-600 hover:bg-red-700 text-white font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-red-500/50"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="6" width="12" height="12" rx="1" />
          </svg>
          Stop
        </button>
      </div>
    )
  }

  if (state === 'uploading') {
    return (
      <div className="bg-card border border-cardBorder rounded-xl p-5 flex items-center gap-3">
        <div className="animate-spin h-4 w-4 border-2 border-teal-400 border-t-transparent rounded-full" />
        <span className="text-textSecondary text-sm">Uploading your answer...</span>
      </div>
    )
  }

  if (onRetryUpload) {
    return (
      <div className="bg-card border border-red-500/30 rounded-xl p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <p className="text-red-400 text-sm font-medium">Your recording could not be uploaded</p>
          {error && <p className="text-red-300/80 text-xs mt-1">{error}</p>}
          <p className="text-textSecondary text-xs mt-1">The recording is kept, so you can send it again.</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button onClick={onStart} className={outlineButtonClass}>
            Record again
          </button>
          <button
            onClick={onRetryUpload}
            className="px-5 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-purple-600 text-white font-semibold text-sm hover:opacity-90 transition-opacity"
          >
            Retry upload
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-card border border-cardBorder rounded-xl p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        {error ? (
          <p className="text-red-400 text-sm">{error}</p>
        ) : (
          <>
            <p className="text-textPrimary text-sm font-medium">Answer as you would in the client interview</p>
            <p className="text-textSecondary text-xs mt-1">
              You have {formatDuration(maxSeconds)}. Recording stops automatically when time is up.
            </p>
          </>
        )}
      </div>
      <button
        onClick={onStart}
        className="flex items-center justify-center gap-2 px-6 py-2.5 rounded-lg bg-gradient-to-r from-cyan-500 to-purple-600 text-white font-semibold text-sm hover:opacity-90 transition-opacity focus:outline-none focus:ring-2 focus:ring-accent/50 shrink-0"
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
        {error ? 'Try again' : 'Record'}
      </button>
    </div>
  )
}
