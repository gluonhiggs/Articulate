import { Link } from 'react-router-dom'
import type { SkillRow, SkillState } from '../../types/interview'

const STATE_PILL: Record<SkillState, string> = {
  no_questions: 'bg-red-500/10 text-red-400 border-red-500/30',
  weak: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
  unpractised: 'bg-white/5 text-gray-400 border-white/10',
  ready: 'bg-teal-500/10 text-teal-400 border-teal-500/30',
}

const actionClass =
  'text-xs px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-gray-300 hover:bg-white/10 transition-colors shrink-0'

export function pillText(row: SkillRow): string {
  if (row.state === 'no_questions') return 'no questions'
  if (row.state === 'unpractised') return 'not practised'
  return `your best ${row.best_score}`
}

/**
 * Ranked skills in the Forecast row shape: rank, name, question count, why it sits
 * there, and one action. draftHref is where "Draft some" goes for a skill with no
 * questions; without one, such a row only shows the gap.
 */
export function SkillRows({ rows, draftHref }: { rows: SkillRow[]; draftHref?: string }) {
  return (
    <div className="space-y-2">
      {rows.map((row, index) => (
        <div key={row.skill} className="flex items-center gap-3 bg-card border border-cardBorder rounded-xl px-4 py-3">
          <span className="text-textSecondary text-sm font-mono w-5 shrink-0">{index + 1}</span>
          <div className="flex-1 min-w-0">
            <span className="text-textPrimary font-medium">{row.label}</span>
            <span className="ml-2 text-xs text-textSecondary">
              {row.question_count} question{row.question_count === 1 ? '' : 's'}
            </span>
          </div>
          <span className={`text-xs px-2 py-0.5 rounded-full border shrink-0 ${STATE_PILL[row.state]}`}>
            {pillText(row)}
          </span>
          {row.question_count > 0 ? (
            <Link to={`/interview/set?skills=${row.skill}`} className={actionClass}>
              Practice now
            </Link>
          ) : (
            draftHref && (
              <Link to={draftHref} className={actionClass}>
                Draft some
              </Link>
            )
          )}
        </div>
      ))}
    </div>
  )
}
