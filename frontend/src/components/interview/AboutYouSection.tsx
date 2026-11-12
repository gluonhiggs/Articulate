import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  draftIntroductionQuestion,
  fetchAboutYou,
  fetchCandidateProfile,
  fetchSkillList,
} from '../../api/interview'
import { createLogger, errorData } from '../../lib/log'
import type { InterviewQuestion } from '../../types/interview'
import { SkillRows } from './SkillRows'
import { outlineButtonClass } from './ui'
import { apiErrorDetail, plural, scoreBand, bandStyle } from './utils'

const log = createLogger('interview/about-you')

function QuestionRow({ question }: { question: InterviewQuestion }) {
  const content = bandStyle(scoreBand(question.latest_content_score))
  return (
    <Link
      to={`/interview/questions/${question.id}`}
      className="flex items-center gap-3 rounded-xl border border-white/5 bg-card/50 px-4 py-3 hover:border-white/10 transition-colors"
    >
      <div className="flex-1 min-w-0">
        <p className="text-sm text-textPrimary">{question.text}</p>
        <p className="text-[11px] text-textSecondary mt-0.5">
          {plural(question.key_points.length, 'key point')} - {Math.round(question.answer_seconds / 60)} min
        </p>
      </div>
      <span className={`text-xs shrink-0 ${content.text}`}>
        {question.latest_content_score ?? '--'}
      </span>
    </Link>
  )
}

export function AboutYouSection() {
  const queryClient = useQueryClient()

  const { data: profile } = useQuery({ queryKey: ['interview', 'profile'], queryFn: fetchCandidateProfile })
  const { data: aboutYou } = useQuery({ queryKey: ['interview', 'about-you'], queryFn: fetchAboutYou })
  const { data: skillList } = useQuery({
    queryKey: ['interview', 'skills', null],
    queryFn: () => fetchSkillList(null),
  })
  const cvSkills = (skillList?.rows ?? []).filter((row) => row.in_cv)

  const draftMutation = useMutation({
    mutationFn: () => {
      log.info('introduction start')
      return draftIntroductionQuestion()
    },
    onSuccess: (pack) => {
      log.info('introduction ok', { questions: pack.questions.length })
      void queryClient.invalidateQueries({ queryKey: ['interview'] })
    },
    onError: (error) => log.error('introduction failed', errorData(error)),
  })

  const questions = aboutYou?.questions.filter((question) => !question.retired) ?? []
  const hasCv = profile?.has_cv ?? false

  return (
    <section className="space-y-2">
      <div className="flex flex-wrap items-baseline gap-2">
        <h2 className="text-textPrimary font-semibold">About you</h2>
        <p className="text-xs text-textSecondary flex-1">
          Questions about your own background, with an answer key written from your CV.
        </p>
      </div>

      {questions.length > 0 && <div className="space-y-2">{questions.map((question) => (
        <QuestionRow key={question.id} question={question} />
      ))}</div>}

      <div className="flex flex-wrap items-center gap-2 pt-1">
        <button
          type="button"
          onClick={() => draftMutation.mutate()}
          disabled={!hasCv || draftMutation.isPending}
          title={hasCv ? 'Write one question from your CV' : 'Add your CV first'}
          className={outlineButtonClass}
        >
          {draftMutation.isPending ? 'Writing...' : questions.length > 0 ? 'Write another' : 'Write from my CV'}
        </button>
        {!hasCv && (
          <span className="text-xs text-textSecondary">
            Add your CV first so the answer key can name your own projects.
          </span>
        )}
      </div>

      {cvSkills.length > 0 && (
        <div className="space-y-2 pt-3">
          <p className="text-xs text-textSecondary">Skills your CV claims, so the ones you will be asked to defend.</p>
          <SkillRows rows={cvSkills} />
        </div>
      )}

      {draftMutation.isError && (
        <p className="text-red-400 text-sm">{apiErrorDetail(draftMutation.error)}</p>
      )}
    </section>
  )
}
