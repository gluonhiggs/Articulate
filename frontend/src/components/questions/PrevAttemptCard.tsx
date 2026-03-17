import type { Attempt } from '../../types'
import { ScoreCircle } from './ScoreCircle'
import { ScoreTags } from './ScoreTags'

export function PrevAttemptCard({
  attempt,
  index,
  isNew,
  onSelect,
}: {
  attempt: Attempt
  index: number
  isNew: boolean
  onSelect: () => void
}) {
  if (attempt.status === 'processing') {
    return (
      <div className={`rounded-xl p-4 bg-card/60 border border-cardBorder ${isNew ? 'slide-in-top' : ''}`}>
        <div className="flex items-center gap-3">
          <span className="text-gray-500 text-xs font-mono">#{index + 1}</span>
          <div className="animate-spin h-3 w-3 border-2 border-teal-400 border-t-transparent rounded-full" />
          <span className="text-gray-500 text-sm">Processing...</span>
        </div>
      </div>
    )
  }

  if (attempt.status === 'failed') {
    return (
      <div className={`rounded-xl p-4 bg-card/60 border border-red-500/20 ${isNew ? 'slide-in-top' : ''}`}>
        <span className="text-gray-500 text-xs font-mono">#{index + 1}</span>
        <p className="text-red-400/60 text-sm mt-1">Failed</p>
      </div>
    )
  }

  return (
    <button
      onClick={onSelect}
      className={`w-full text-left rounded-xl p-4 bg-card/50 border border-white/5 flex gap-4 opacity-70 hover:opacity-100 transition-all hover:border-white/10 ${isNew ? 'slide-in-top' : ''}`}
    >
      <div className="w-8 h-8 shrink-0 rounded-full bg-white/5 flex items-center justify-center border border-white/10">
        <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 text-gray-300 ml-0.5" viewBox="0 0 24 24" fill="currentColor">
          <polygon points="5 3 19 12 5 21 5 3" />
        </svg>
      </div>

      <div className="flex-1 min-w-0 space-y-2">
        <p className="text-sm leading-relaxed text-gray-300 line-clamp-2">
          {attempt.transcript ?? 'No transcript'}
        </p>
        <ScoreTags attempt={attempt} />
      </div>

      <div className="shrink-0 flex items-center">
        <ScoreCircle score={attempt.score} size="sm" />
      </div>
    </button>
  )
}
