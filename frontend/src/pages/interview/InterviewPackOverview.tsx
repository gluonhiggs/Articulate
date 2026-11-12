import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  fetchInterviewPack,
  fetchSkillList,
  interviewPackExportUrl,
  interviewPackReportUrl,
} from '../../api/interview'
import { PackQuestionRow } from '../../components/interview/PackQuestionRow'
import { JobIntroduction } from '../../components/interview/JobIntroduction'
import { SkillRows } from '../../components/interview/SkillRows'
import { outlineButtonClass } from '../../components/interview/ui'
import {
  apiErrorDetail,
  groupByTopic,
  LEVEL_LABELS,
  pickPracticeQuestion,
  ROLE_LABELS,
} from '../../components/interview/utils'
import { PACK_FILE_ACCEPT, useImportPack } from '../../hooks/useImportPack'
import type { InterviewPackDetail } from '../../types/interview'

export function InterviewPackOverview() {
  const { packId: packIdStr } = useParams<{ packId: string }>()
  const packId = Number(packIdStr)
  const navigate = useNavigate()
  const [showJobDescription, setShowJobDescription] = useState(false)
  const importPack = useImportPack()

  const { data: pack, isLoading, isError, error } = useQuery<InterviewPackDetail>({
    queryKey: ['interview', 'pack', packId],
    queryFn: () => fetchInterviewPack(packId),
    enabled: !isNaN(packId),
    staleTime: 0,
  })

  const { data: skillList } = useQuery({
    queryKey: ['interview', 'skills', packId],
    queryFn: () => fetchSkillList(packId),
    enabled: !isNaN(packId),
  })
  const jobSkills = (skillList?.rows ?? []).filter((row) => row.in_job)

  const topicGroups = useMemo(() => groupByTopic(pack?.questions ?? []), [pack])
  const practiceQuestion = useMemo(() => pickPracticeQuestion(pack?.questions ?? []), [pack])

  return (
    <div className="flex flex-col min-h-screen">
      <div className="bg-sidebar border-b border-cardBorder px-6 py-4 sticky top-0 z-10 flex items-center gap-2 text-sm text-textSecondary">
        <Link to="/interview?tab=jobs" className="hover:text-textPrimary transition-colors">
          Interview
        </Link>
        <span className="text-[10px]">/</span>
        <span className="text-textPrimary font-medium line-clamp-1">{pack?.title ?? (isLoading ? 'Loading...' : 'Questionnaire')}</span>
      </div>

      <div className="p-6 flex-1 space-y-6 max-w-5xl w-full mx-auto">
        {isLoading ? (
          <>
            <div className="h-32 bg-card animate-pulse rounded-xl" />
            <div className="h-40 bg-card animate-pulse rounded-xl" />
            <div className="h-64 bg-card animate-pulse rounded-xl" />
          </>
        ) : isError || isNaN(packId) || !pack ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <p className="text-red-400 text-lg">Could not load this questionnaire</p>
            <p className="text-textSecondary text-sm mt-2">
              {isNaN(packId) ? 'Invalid questionnaire link.' : apiErrorDetail(error)}
            </p>
            <Link to="/interview?tab=jobs" className={`mt-4 ${outlineButtonClass}`}>
              Back to questionnaires
            </Link>
          </div>
        ) : (
          <>
            <div className="bg-card border border-cardBorder rounded-xl p-5">
              <div className="flex flex-col gap-4">
                <div className="min-w-0">
                  <h1 className="text-2xl font-bold text-textPrimary leading-tight">{pack.title}</h1>
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    <span className="text-xs bg-teal-500/10 text-teal-400 border border-teal-500/30 px-2 py-0.5 rounded-full">
                      {ROLE_LABELS[pack.role]}
                    </span>
                    <span className="text-xs bg-white/5 text-gray-400 border border-white/10 px-2 py-0.5 rounded-full">
                      {LEVEL_LABELS[pack.level]}
                    </span>
                    <span className="text-xs text-textSecondary">
                      v{pack.version}
                      {pack.author && ` \u00B7 prepared by ${pack.author}`}
                    </span>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={() => practiceQuestion && navigate(`/interview/questions/${practiceQuestion.id}`)}
                    disabled={!practiceQuestion}
                    title={practiceQuestion ? practiceQuestion.text : 'This questionnaire has no questions yet'}
                    className="px-5 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-purple-600 text-white font-semibold text-sm hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Practice
                  </button>
                  <Link
                    to={`/interview/packs/${pack.id}/studio`}
                    title="Write questions, approve the answer key, add sources and the glossary"
                    className={outlineButtonClass}
                  >
                    Edit questionnaire
                  </Link>
                  <a
                    href={interviewPackExportUrl(pack.id)}
                    download
                    title="Save the questions and answer key as a file you can share"
                    className={outlineButtonClass}
                  >
                    Download questionnaire
                  </a>
                  <a
                    href={interviewPackReportUrl(pack.id)}
                    download
                    title="Save your transcripts and scores for every answer in this questionnaire"
                    className={outlineButtonClass}
                  >
                    Download my results
                  </a>
                  {/* Beside the exports, because a download and its matching upload belong together. */}
                  <input
                    ref={importPack.inputRef}
                    type="file"
                    accept={PACK_FILE_ACCEPT}
                    onChange={importPack.onFileChange}
                    className="hidden"
                  />
                  <button
                    onClick={importPack.open}
                    disabled={importPack.pending}
                    title="A questionnaire file someone shared with you, or a plain list of questions (.txt, .docx, .pdf)"
                    className={outlineButtonClass}
                  >
                    {importPack.pending ? 'Uploading...' : 'Upload another questionnaire'}
                  </button>
                </div>
              </div>

              {pack.job_description.trim() && (
                <div className="mt-4 pt-3 border-t border-white/5">
                  <button
                    onClick={() => setShowJobDescription((v) => !v)}
                    aria-expanded={showJobDescription}
                    className="text-xs text-textSecondary hover:text-textPrimary transition-colors"
                  >
                    {showJobDescription ? '\u25BE Hide job description' : '\u25B8 Show job description'}
                  </button>
                  {showJobDescription && (
                    <p className="mt-2 text-sm text-gray-300 whitespace-pre-line leading-relaxed">
                      {pack.job_description}
                    </p>
                  )}
                </div>
              )}
            </div>

            {importPack.error && (
              <div className="bg-red-900/20 border border-red-500/30 rounded-xl p-4 flex items-start justify-between gap-4">
                <div>
                  <p className="text-red-400 text-sm font-medium">Could not import this questionnaire file</p>
                  <p className="text-red-400/80 text-xs mt-1 whitespace-pre-line break-words">
                    {apiErrorDetail(importPack.error)}
                  </p>
                </div>
                <button onClick={importPack.reset} className="text-xs text-red-400/80 hover:text-red-300 shrink-0">
                  Dismiss
                </button>
              </div>
            )}

            <JobIntroduction
              packId={pack.id}
              hasIntroduction={pack.questions.some((question) => question.kind === 'behavioural' && !question.retired)}
            />

            <section className="space-y-2">
              <div className="flex items-baseline gap-2">
                <h2 className="text-textPrimary font-semibold">Skills for this job</h2>
                <p className="text-xs text-textSecondary">Hardest first. Practice now runs every question on that skill.</p>
              </div>
              {jobSkills.length > 0 ? (
                <SkillRows rows={jobSkills} draftHref={`/interview/packs/${pack.id}/studio`} />
              ) : (
                <p className="text-sm text-textSecondary">
                  The job description names no skills yet. Add one under Edit questionnaire, Details.
                </p>
              )}
            </section>

            {pack.questions.length === 0 ? (
              <div className="bg-card/50 border border-dashed border-white/10 rounded-xl p-8 text-center">
                <p className="text-gray-400 text-sm">No questions in this questionnaire yet</p>
                <p className="text-gray-500 text-xs mt-1">Use Edit questionnaire to write or draft questions.</p>
              </div>
            ) : (
              <div className="space-y-6">
                {topicGroups.map((group) => (
                  <div key={group.topic}>
                    <p className="text-xs font-semibold text-textSecondary uppercase tracking-wider mb-2">
                      {group.topic}
                    </p>
                    <div className="space-y-2">
                      {group.items.map((question) => (
                        <PackQuestionRow key={question.id} question={question} />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
