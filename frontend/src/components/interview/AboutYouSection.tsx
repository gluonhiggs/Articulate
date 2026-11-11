import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { draftIntroductionQuestion, fetchAboutYou, fetchCandidateProfile } from '../../api/interview'
import { createLogger, errorData } from '../../lib/log'
import type { InterviewPackSummary, InterviewQuestion } from '../../types/interview'
import { outlineButtonClass } from './ui'
import { apiErrorDetail, plural, scoreBand, bandStyle } from './utils'

const log = createLogger('interview/about-you')

const NO_JOB = ''

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

export function AboutYouSection({ jobs }: { jobs: InterviewPackSummary[] }) {
  const queryClient = useQueryClient()
  const [jobPackId, setJobPackId] = useState<string>(NO_JOB)

  const { data: profile } = useQuery({ queryKey: ['interview', 'profile'], queryFn: fetchCandidateProfile })
  const { data: aboutYou } = useQuery({ queryKey: ['interview', 'about-you'], queryFn: fetchAboutYou })

  const draftMutation = useMutation({
    mutationFn: () => {
      log.info('introduction start', { jobPackId })
      return draftIntroductionQuestion(jobPackId === NO_JOB ? null : Number(jobPackId))
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
        <Link to="/interview/cv" className="text-xs text-accent hover:underline shrink-0">
          {hasCv ? 'Edit my CV' : 'Add my CV'}
        </Link>
      </div>

      {questions.length > 0 && <div className="space-y-2">{questions.map((question) => (
        <QuestionRow key={question.id} question={question} />
      ))}</div>}

      <div className="flex flex-wrap items-center gap-2 pt-1">
        {jobs.length > 0 && (
          <select
            value={jobPackId}
            onChange={(event) => setJobPackId(event.target.value)}
            disabled={!hasCv || draftMutation.isPending}
            title="Aim the question at one client, so it asks you to connect your history to what they want"
            className="bg-card border border-cardBorder rounded-lg px-3 py-2 text-sm text-textPrimary disabled:opacity-50"
          >
            <option value={NO_JOB}>No specific job</option>
            {jobs.map((job) => (
              <option key={job.id} value={String(job.id)}>
                {job.title}
              </option>
            ))}
          </select>
        )}
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

      {draftMutation.isError && (
        <p className="text-red-400 text-sm">{apiErrorDetail(draftMutation.error)}</p>
      )}
    </section>
  )
}
