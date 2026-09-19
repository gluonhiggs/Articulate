import { Link } from 'react-router-dom'
import type { InterviewPackSummary } from '../../types/interview'
import { bandStyle, LEVEL_LABELS, ROLE_LABELS, scoreBand } from './utils'

export function PackCard({ pack }: { pack: InterviewPackSummary }) {
  const average = pack.average_content_score === null ? null : Math.round(pack.average_content_score)
  const averageStyle = bandStyle(scoreBand(average))

  return (
    <Link
      to={`/interview/packs/${pack.id}`}
      className="block bg-card rounded-xl p-4 border border-cardBorder transition-all duration-200 hover:border-accent/50 hover:shadow-lg hover:shadow-accent/5 hover:-translate-y-0.5 focus:outline-none focus:ring-2 focus:ring-accent/50"
    >
      <div className="h-0.5 w-full rounded-full mb-3 bg-gradient-to-r from-cyan-500/50 to-purple-500/50" />

      <p className="text-textPrimary text-sm font-semibold leading-snug line-clamp-2">{pack.title}</p>

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <span className="text-xs bg-teal-500/10 text-teal-400 border border-teal-500/30 px-2 py-0.5 rounded-full">
          {ROLE_LABELS[pack.role]}
        </span>
        <span className="text-xs bg-white/5 text-gray-400 border border-white/10 px-2 py-0.5 rounded-full">
          {LEVEL_LABELS[pack.level]}
        </span>
        <span className="text-xs text-textSecondary">v{pack.version}</span>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2 text-center">
        <div className="bg-background rounded-lg py-2">
          <p className="text-textPrimary font-semibold text-sm">{pack.question_count}</p>
          <p className="text-textSecondary text-[11px]">Questions</p>
        </div>
        <div className="bg-background rounded-lg py-2">
          <p className="text-textPrimary font-semibold text-sm">{pack.answered_question_count}</p>
          <p className="text-textSecondary text-[11px]">Answered</p>
        </div>
        <div className="bg-background rounded-lg py-2">
          <p className={`font-semibold text-sm ${average === null ? 'text-textSecondary' : averageStyle.text}`}>
            {average ?? '--'}
          </p>
          <p className="text-textSecondary text-[11px]">Avg content</p>
        </div>
      </div>

      {pack.author && <p className="mt-3 text-xs text-textSecondary truncate">Prepared by {pack.author}</p>}
    </Link>
  )
}
