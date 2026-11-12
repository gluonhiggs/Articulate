import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { fetchInterviewPacks, fetchSkillList } from '../../api/interview'
import { apiErrorDetail } from '../../components/interview/utils'
import type { SkillRow, SkillState } from '../../types/interview'

type Source = 'job' | 'cv' | 'all'

const SOURCES: { id: Source; label: string; blurb: string }[] = [
  { id: 'job', label: 'For a job', blurb: 'Skills this client asks for, hardest first.' },
  { id: 'cv', label: 'From my CV', blurb: 'Skills you claim, so the ones you must defend.' },
  { id: 'all', label: 'All skills', blurb: 'Every skill your questions cover.' },
]

const STATE_PILL: Record<SkillState, string> = {
  no_questions: 'bg-red-500/10 text-red-400 border-red-500/30',
  weak: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
  unpractised: 'bg-white/5 text-gray-400 border-white/10',
  ready: 'bg-teal-500/10 text-teal-400 border-teal-500/30',
}

function pillText(row: SkillRow): string {
  const where = row.in_job ? 'in the job' : row.in_cv ? 'in your CV' : 'not asked for'
  if (row.state === 'no_questions') return `${where} - no questions`
  if (row.state === 'unpractised') return `${where} - not practised`
  return `${where} - your best ${row.best_score}`
}

function visible(row: SkillRow, source: Source): boolean {
  if (source === 'job') return row.in_job
  if (source === 'cv') return row.in_cv
  return row.question_count > 0
}

export function SkillsPage() {
  const navigate = useNavigate()
  const [source, setSource] = useState<Source>('job')
  const [jobPackId, setJobPackId] = useState<number | null>(null)

  const { data: packs } = useQuery({ queryKey: ['interview', 'packs'], queryFn: fetchInterviewPacks })
  const selectedJob = jobPackId ?? packs?.[0]?.id ?? null

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['interview', 'skills', selectedJob],
    queryFn: () => fetchSkillList(selectedJob),
  })

  const rows = (data?.rows ?? []).filter((row) => visible(row, source))
  const blurb = SOURCES.find((item) => item.id === source)?.blurb ?? ''

  return (
    <div className="flex flex-col min-h-screen">
      <div className="bg-sidebar border-b border-cardBorder px-6 py-4 sticky top-0 z-10 flex items-center gap-2 text-sm text-textSecondary">
        <Link to="/interview" className="hover:text-textPrimary transition-colors">
          Interview
        </Link>
        <span className="text-[10px]">/</span>
        <span className="text-textPrimary font-medium">Practice by skill</span>
      </div>

      <div className="p-6 flex-1 space-y-4 max-w-3xl w-full mx-auto">
        <div className="flex flex-wrap items-center gap-2">
          {SOURCES.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setSource(item.id)}
              className={`px-3.5 py-1.5 rounded-lg text-sm border transition-colors ${
                source === item.id
                  ? 'bg-accent/10 text-accent border-accent/30'
                  : 'bg-card/50 text-textSecondary border-white/10 hover:border-white/20'
              }`}
            >
              {item.label}
            </button>
          ))}
          {source === 'job' && packs && packs.length > 0 && (
            <select
              value={String(selectedJob ?? '')}
              onChange={(event) => setJobPackId(Number(event.target.value))}
              className="ml-auto bg-card border border-cardBorder rounded-lg px-3 py-1.5 text-sm text-textPrimary"
            >
              {packs.map((pack) => (
                <option key={pack.id} value={String(pack.id)}>
                  {pack.title}
                </option>
              ))}
            </select>
          )}
        </div>

        <p className="text-xs text-textSecondary">{blurb}</p>

        {isLoading && <div className="h-40 bg-card animate-pulse rounded-xl" />}
        {isError && <p className="text-red-400 text-sm">{apiErrorDetail(error)}</p>}

        {rows.length === 0 && !isLoading && (
          <div className="bg-card/50 border border-dashed border-white/10 rounded-xl p-8 text-center">
            <p className="text-gray-400 text-sm">Nothing to show yet</p>
            <p className="text-gray-500 text-xs mt-1">
              {source === 'cv'
                ? 'Add your CV so the skills you claim can be listed.'
                : 'Write some questions first, or pick another job.'}
            </p>
          </div>
        )}

        <div className="space-y-2">
          {rows.map((row, index) => (
            <div
              key={row.skill}
              className="flex items-center gap-3 bg-card border border-cardBorder rounded-xl px-4 py-3"
            >
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
              {row.question_count === 0 ? (
                <Link
                  to={`/interview/packs/${selectedJob ?? ''}/studio`}
                  className="text-xs px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-gray-300 hover:bg-white/10 transition-colors shrink-0"
                >
                  Draft some
                </Link>
              ) : (
                <button
                  type="button"
                  onClick={() => navigate(`/interview/set?skills=${row.skill}`)}
                  className="text-xs px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-gray-300 hover:bg-white/10 transition-colors shrink-0"
                >
                  Practice now
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
