import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useId, useState } from 'react'
import { draftInterviewQuestions } from '../../../api/interview'
import { createLogger, errorData } from '../../../lib/log'
import type { InterviewDraftRequest, InterviewPackDetail } from '../../../types/interview'
import {
  DRAFT_TIMEOUT_MINUTES,
  MAX_DRAFT_SOURCES,
  describeDraftError,
  isRateLimitError,
  isTimeoutError,
  plural,
  uniqueTopics,
  type StudioTab,
} from './studioModel'
import {
  Field,
  Notice,
  Spinner,
  cardClass,
  inputClass,
  primaryButtonClass,
  secondaryButtonClass,
} from './studioUi'

const LATE_DRAFT_REFRESH_DELAYS_MS = [60_000, 180_000]
const log = createLogger('interview/studio')

interface DraftTabProps {
  pack: InterviewPackDetail
  onDrafted: (questionIds: number[]) => void
  onOpenTab: (tab: StudioTab) => void
}

export function DraftTab({ pack, onDrafted, onOpenTab }: DraftTabProps) {
  const queryClient = useQueryClient()
  const topicsListId = useId()
  const [topic, setTopic] = useState('')
  const [count, setCount] = useState(3)
  const [excludedSourceIds, setExcludedSourceIds] = useState<Set<number>>(new Set())
  const [elapsedSeconds, setElapsedSeconds] = useState(0)

  const draftMutation = useMutation({
    mutationFn: (request: InterviewDraftRequest) => {
      log.info('draft start', {
        packId: pack.id,
        topic: request.topic,
        count: request.count,
        sources: request.source_ids.length,
      })
      return draftInterviewQuestions(pack.id, request)
    },
    onSuccess: async (questions) => {
      log.info('draft ok', { packId: pack.id, drafted: questions.length, ids: questions.map((q) => q.id) })
      await queryClient.invalidateQueries({ queryKey: ['interview'] })
      onDrafted(questions.map((question) => question.id))
    },
    onError: (error) => {
      const timedOut = isTimeoutError(error)
      log.error(`draft failed for pack ${pack.id} (timeout=${timedOut})`, errorData(error))
      const refresh = () => void queryClient.invalidateQueries({ queryKey: ['interview', 'pack', pack.id] })
      refresh()
      // The backend keeps drafting after the browser gives up and saves the questions when it finishes.
      if (timedOut) LATE_DRAFT_REFRESH_DELAYS_MS.forEach((delay) => setTimeout(refresh, delay))
    },
  })

  useEffect(() => {
    if (!draftMutation.isPending) return
    const startedAt = Date.now()
    setElapsedSeconds(0)
    const timer = setInterval(() => setElapsedSeconds(Math.round((Date.now() - startedAt) / 1000)), 1000)
    return () => clearInterval(timer)
  }, [draftMutation.isPending])

  const selectedSourceIds = pack.sources.map((source) => source.id).filter((id) => !excludedSourceIds.has(id))
  const tooManySources = selectedSourceIds.length > MAX_DRAFT_SOURCES

  function toggleSource(sourceId: number) {
    setExcludedSourceIds((prev) => {
      const next = new Set(prev)
      if (next.has(sourceId)) next.delete(sourceId)
      else next.add(sourceId)
      return next
    })
  }

  function handleDraft() {
    draftMutation.mutate({ topic: topic.trim(), count, source_ids: selectedSourceIds })
  }

  return (
    <div className="space-y-4">
      <Notice tone="info">
        The AI drafts questions a client interviewer would ask for this role and level, with key points, misconceptions
        and follow-ups. Drafts are saved unapproved: nothing is graded until you review and approve the key points in
        the Questions tab. Drafting uses the free Gemini quota.
      </Notice>

      {!pack.job_description.trim() && (
        <Notice tone="warning">
          This questionnaire has no job description. Add one in Details so the questions match the client role.
        </Notice>
      )}

      <div className={cardClass}>
        <datalist id={topicsListId}>
          {uniqueTopics(pack.questions).map((item) => (
            <option key={item} value={item} />
          ))}
        </datalist>
        <fieldset disabled={draftMutation.isPending} className="space-y-4 min-w-0">
          <div className="grid grid-cols-1 md:grid-cols-[1fr_10rem] gap-4">
            <Field label="Topic">
              <input
                type="text"
                list={topicsListId}
                maxLength={100}
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="e.g. Spark performance tuning"
                className={inputClass}
              />
            </Field>
            <Field label="Questions">
              <select value={count} onChange={(e) => setCount(Number(e.target.value))} className={inputClass}>
                {[1, 2, 3, 4, 5].map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <div>
            <p className="text-xs font-medium text-textSecondary mb-2">Sources</p>
            {pack.sources.length === 0 ? (
              <div className="flex flex-wrap items-center gap-3">
                <p className="text-xs text-gray-500 flex-1">
                  No sources. Drafting still works, but key points will have no source quotes to verify.
                </p>
                <button type="button" className={secondaryButtonClass} onClick={() => onOpenTab('sources')}>
                  Add sources
                </button>
              </div>
            ) : (
              <div className="space-y-1.5">
                {pack.sources.map((source) => (
                  <label key={source.id} className="flex items-center gap-2 text-sm text-textPrimary cursor-pointer">
                    <input
                      type="checkbox"
                      checked={!excludedSourceIds.has(source.id)}
                      onChange={() => toggleSource(source.id)}
                      className="accent-cyan-500"
                    />
                    <span className="truncate">{source.title}</span>
                    <span className="text-xs text-textSecondary shrink-0">
                      {source.content_length.toLocaleString()} chars
                    </span>
                  </label>
                ))}
                {tooManySources && (
                  <p className="text-xs text-amber-300">Select at most {MAX_DRAFT_SOURCES} sources.</p>
                )}
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button type="button" className={primaryButtonClass} disabled={!topic.trim() || tooManySources} onClick={handleDraft}>
              {draftMutation.isPending && <Spinner />}
              {draftMutation.isPending ? 'Drafting...' : `Draft ${plural(count, 'question')}`}
            </button>
            {draftMutation.isPending && (
              <span className="text-xs text-textSecondary">
                {elapsedSeconds}s elapsed. This can take up to {DRAFT_TIMEOUT_MINUTES} minutes.
              </span>
            )}
          </div>
        </fieldset>
      </div>

      {draftMutation.isError && (
        <Notice tone={isRateLimitError(draftMutation.error) ? 'warning' : 'error'}>
          {describeDraftError(draftMutation.error)}
        </Notice>
      )}

      {draftMutation.isSuccess && (
        <Notice tone="success">
          <div className="flex flex-wrap items-center gap-3">
            <span className="flex-1">
              Drafted {plural(draftMutation.data.length, 'question')}. Review and approve their key points before
              candidates practice.
            </span>
            <button type="button" className={secondaryButtonClass} onClick={() => onOpenTab('questions')}>
              Review drafts
            </button>
          </div>
        </Notice>
      )}
    </div>
  )
}
