import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchCandidateProfile, fetchSkillList } from '../../api/interview'
import { AboutYouSection } from './AboutYouSection'
import { SkillRows } from './SkillRows'
import { apiErrorDetail } from './utils'

export type InterviewTab = 'jobs' | 'cv' | 'skills'

export const INTERVIEW_TABS: { id: InterviewTab; label: string }[] = [
  { id: 'cv', label: 'CV' },
  { id: 'jobs', label: 'Jobs' },
  { id: 'skills', label: 'Skills' },
]

export function TabButtons({ current, onSelect }: { current: InterviewTab; onSelect: (tab: InterviewTab) => void }) {
  return (
    <div className="flex items-center gap-2">
      {INTERVIEW_TABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onSelect(tab.id)}
          className={`px-4 py-1.5 rounded-lg text-sm border transition-colors ${
            current === tab.id
              ? 'bg-accent/10 text-accent border-accent/30'
              : 'bg-card/50 text-textSecondary border-white/10 hover:border-white/20'
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}

export function CvTab() {
  const { data: profile } = useQuery({ queryKey: ['interview', 'profile'], queryFn: fetchCandidateProfile })
  const characters = profile?.cv_text.length ?? 0

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3 bg-card border border-cardBorder rounded-xl px-4 py-3">
        <div className="flex-1 min-w-0">
          <p className="text-sm text-textPrimary">
            {profile?.has_cv ? profile.full_name || 'Your CV' : 'No CV yet'}
          </p>
          <p className="text-xs text-textSecondary mt-0.5">
            {profile?.has_cv
              ? `${characters.toLocaleString()} characters${profile.cv_filename ? ` - from ${profile.cv_filename}` : ''}`
              : 'Add your CV so the questions can be about your own projects.'}
          </p>
        </div>
        <Link
          to="/interview/cv"
          className="text-xs px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-gray-300 hover:bg-white/10 transition-colors shrink-0"
        >
          {profile?.has_cv ? 'Edit my CV' : 'Add my CV'}
        </Link>
      </div>
      <AboutYouSection />
    </div>
  )
}

export function SkillsTab() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['interview', 'skills', null],
    queryFn: () => fetchSkillList(null),
  })
  const rows = (data?.rows ?? []).filter((row) => row.question_count > 0)

  return (
    <div className="space-y-3">
      <p className="text-xs text-textSecondary">
        Questions across skills. To add a skill, upload or create a questionnaire that covers it.
      </p>
      {isLoading && <div className="h-40 bg-card animate-pulse rounded-xl" />}
      {isError && <p className="text-red-400 text-sm">{apiErrorDetail(error)}</p>}
      {!isLoading && rows.length === 0 && (
        <p className="text-sm text-textSecondary">No skills yet. Upload or create a questionnaire to add some.</p>
      )}
      <SkillRows rows={rows} />
    </div>
  )
}
