import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { fetchSkillSet } from '../../api/interview'
import { apiErrorDetail, bandStyle, plural, scoreBand } from '../../components/interview/utils'

export function SkillSetPage() {
  const [searchParams] = useSearchParams()
  const skills = (searchParams.get('skills') ?? '').split(',').filter(Boolean)

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['interview', 'skill-set', skills.join(',')],
    queryFn: () => fetchSkillSet(skills),
    enabled: skills.length > 0,
  })

  const questions = data?.questions ?? []
  const setQuery = skills.join(',')

  return (
    <div className="flex flex-col min-h-screen">
      <div className="bg-sidebar border-b border-cardBorder px-6 py-4 sticky top-0 z-10 flex items-center gap-2 text-sm text-textSecondary">
        <Link to="/interview" className="hover:text-textPrimary transition-colors">
          Interview
        </Link>
        <span className="text-[10px]">/</span>
        <Link to="/interview/skills" className="hover:text-textPrimary transition-colors">
          Practice by skill
        </Link>
        <span className="text-[10px]">/</span>
        <span className="text-textPrimary font-medium">{data?.labels.join(', ') || 'Set'}</span>
      </div>

      <div className="p-6 flex-1 space-y-4 max-w-3xl w-full mx-auto">
        <div className="flex flex-wrap items-baseline gap-2">
          <h1 className="text-xl font-semibold text-textPrimary">{data?.labels.join(', ') || 'Set'}</h1>
          <span className="text-sm text-textSecondary flex-1">{plural(questions.length, 'question')}</span>
          {questions.length > 0 && (
            <Link
              to={`/interview/questions/${questions[0].id}?set=${encodeURIComponent(setQuery)}`}
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-purple-600 text-white font-semibold text-sm hover:opacity-90 transition-opacity"
            >
              Start
            </Link>
          )}
        </div>

        {isLoading && <div className="h-40 bg-card animate-pulse rounded-xl" />}
        {isError && <p className="text-red-400 text-sm">{apiErrorDetail(error)}</p>}

        {!isLoading && questions.length === 0 && (
          <div className="bg-card/50 border border-dashed border-white/10 rounded-xl p-8 text-center">
            <p className="text-gray-400 text-sm">No questions carry these skills yet</p>
            <p className="text-gray-500 text-xs mt-1">Draft some in a questionnaire, then come back.</p>
          </div>
        )}

        <div className="space-y-2">
          {questions.map((question) => {
            const content = bandStyle(scoreBand(question.latest_content_score))
            return (
              <Link
                key={question.id}
                to={`/interview/questions/${question.id}?set=${encodeURIComponent(setQuery)}`}
                className="flex items-start gap-3 bg-card border border-cardBorder rounded-xl px-4 py-3 hover:border-white/20 transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-textPrimary">{question.text}</p>
                  <p className="text-[11px] text-textSecondary mt-1">
                    {question.pack_title}
                    {' - '}
                    {question.matched.join(', ')}
                  </p>
                </div>
                <span className={`text-sm shrink-0 ${content.text}`}>{question.latest_content_score ?? '--'}</span>
              </Link>
            )
          })}
        </div>
      </div>
    </div>
  )
}
