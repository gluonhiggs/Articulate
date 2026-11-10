import { Link } from 'react-router-dom'
import type { InterviewQuestion } from '../../types/interview'
import { approvedKeyPointCount, bandStyle, plural, scoreBand } from './utils'

function ScorePill({ label, score }: { label: string; score: number | null }) {
  const style = bandStyle(scoreBand(score))
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border whitespace-nowrap ${style.badge}`}>
      {label} {score ?? '--'}
    </span>
  )
}

export function PackQuestionRow({ question }: { question: InterviewQuestion }) {
  const hasAnswerKey = approvedKeyPointCount(question) > 0

  return (
    <Link
      to={`/interview/questions/${question.id}`}
      className="flex flex-col sm:flex-row sm:items-center gap-3 bg-card border border-cardBorder rounded-xl px-4 py-3 hover:border-accent/40 transition-colors"
    >
      <div className="flex-1 min-w-0">
        <p className="text-textPrimary text-sm leading-snug line-clamp-2">{question.text}</p>
        <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-textSecondary">
          <span>{plural(question.answer_count, 'graded answer')}</span>
          {question.follow_ups.length > 0 && <span>{plural(question.follow_ups.length, 'follow-up')}</span>}
          {!hasAnswerKey && (
            <span
              className="text-amber-400 border border-amber-400/30 rounded px-1.5 py-0.5"
              title="Content cannot be graded until key points are approved in the pack editor"
            >
              {'\u26A0'} No approved key points
            </span>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <ScorePill label="Content" score={question.latest_content_score} />
        <ScorePill label="Delivery" score={question.latest_delivery_score} />
      </div>
    </Link>
  )
}
