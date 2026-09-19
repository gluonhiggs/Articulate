import type { InterviewAnswer } from '../../types/interview'
import { ANSWER_STATUS_LABELS, bandStyle, isAnswerInProgress, parseServerDate, scoreBand } from './utils'

export function AnswerHistory({
  answers,
  activeAnswerId,
  onSelect,
}: {
  answers: InterviewAnswer[]
  activeAnswerId: number | null
  onSelect: (answer: InterviewAnswer) => void
}) {
  return (
    <div>
      <p className="text-xs font-semibold text-textSecondary uppercase tracking-wider mb-2">Previous answers</p>
      <div className="space-y-2">
        {answers.map((answer) => {
          const content = bandStyle(answer.content_band)
          const delivery = bandStyle(scoreBand(answer.delivery?.score ?? null))
          const isActive = answer.id === activeAnswerId
          return (
            <button
              key={answer.id}
              onClick={() => onSelect(answer)}
              className={[
                'w-full text-left rounded-xl px-4 py-3 border flex items-center gap-3 transition-colors',
                isActive
                  ? 'bg-card border-accent/40'
                  : 'bg-card/50 border-white/5 opacity-80 hover:opacity-100 hover:border-white/10',
              ].join(' ')}
            >
              <div className="flex-1 min-w-0">
                <p className="text-xs text-textSecondary">
                  {parseServerDate(answer.created_at).toLocaleString()}
                  {answer.duration_seconds !== null && ` \u00B7 ${Math.round(answer.duration_seconds)}s`}
                </p>
                <p className="text-sm text-gray-300 line-clamp-1 mt-0.5">
                  {answer.transcript ?? ANSWER_STATUS_LABELS[answer.status]}
                </p>
              </div>
              {answer.status === 'graded' ? (
                <div className="flex items-center gap-2 shrink-0">
                  <span className={`text-xs px-2 py-0.5 rounded-full border ${content.badge}`}>
                    Content {answer.content_score ?? '--'}
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded-full border ${delivery.badge}`}>
                    Delivery {answer.delivery?.score ?? '--'}
                  </span>
                </div>
              ) : (
                <span
                  className={[
                    'text-xs px-2 py-0.5 rounded-full border shrink-0 flex items-center gap-1.5',
                    answer.status.startsWith('failed')
                      ? 'bg-red-500/10 text-red-400 border-red-500/30'
                      : 'bg-amber-500/10 text-amber-400 border-amber-500/30',
                  ].join(' ')}
                >
                  {isAnswerInProgress(answer.status) && (
                    <span className="animate-spin h-2.5 w-2.5 border-2 border-amber-400 border-t-transparent rounded-full" />
                  )}
                  {ANSWER_STATUS_LABELS[answer.status]}
                </span>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
