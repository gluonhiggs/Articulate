import type { Question } from '../../types'
import { ScoreBadge } from './ScoreBadge'

interface QuestionCardProps {
  question: Question
  onClick: (question: Question) => void
}

export function QuestionCard({ question, onClick }: QuestionCardProps) {
  const hasScore = question.latest_score !== null

  return (
    <button
      onClick={() => onClick(question)}
      className={[
        'w-full text-left bg-card rounded-xl p-4 border transition-all duration-200',
        'hover:border-accent/50 hover:shadow-lg hover:shadow-accent/5 hover:-translate-y-0.5',
        'focus:outline-none focus:ring-2 focus:ring-accent/50',
        hasScore ? 'border-purple-500/30' : 'border-cardBorder',
      ].join(' ')}
    >
      {/* Gradient top accent line */}
      <div
        className={[
          'h-0.5 w-full rounded-full mb-3',
          hasScore
            ? 'bg-gradient-to-r from-purple-500 to-cyan-500'
            : 'bg-gradient-to-r from-cyan-500/50 to-purple-500/50',
        ].join(' ')}
      />

      <div className="flex items-start justify-between gap-3">
        <p className="text-textPrimary text-sm font-medium leading-snug flex-1 line-clamp-3">
          {question.text}
        </p>
        <div className="flex-shrink-0">
          <ScoreBadge score={question.latest_score} size="sm" />
        </div>
      </div>

      {question.bullet_points && question.bullet_points.length > 0 && (
        <ul className="mt-3 space-y-1">
          {question.bullet_points.slice(0, 3).map((bp, i) => (
            <li key={i} className="text-xs text-textSecondary flex items-start gap-1.5">
              <span className="text-accent mt-0.5">•</span>
              <span className="line-clamp-1">{bp}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3 flex items-center justify-between">
        <span className="text-xs text-textSecondary">Part {question.part}</span>
        {question.category && (
          <span className="text-xs text-textSecondary capitalize bg-background px-2 py-0.5 rounded-full">
            {question.category}
          </span>
        )}
      </div>
    </button>
  )
}
