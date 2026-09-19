import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createInterviewQuestion, retireInterviewQuestion, updateInterviewQuestion } from '../../../api/interview'
import type { InterviewQuestion, InterviewQuestionInput } from '../../../types/interview'
import { apiErrorDetail } from '../utils'
import { FollowUpsEditor } from './FollowUpsEditor'
import { KeyPointsEditor } from './KeyPointsEditor'
import { MisconceptionsEditor } from './MisconceptionsEditor'
import {
  ANSWER_SECONDS_MAX,
  ANSWER_SECONDS_MIN,
  countApproved,
  hasUnapprovedKeyPoints,
  plural,
  questionErrors,
  questionWarnings,
  toQuestionPayload,
} from './studioModel'
import {
  Badge,
  ChevronIcon,
  Field,
  IssueList,
  Notice,
  Spinner,
  dangerButtonClass,
  inputClass,
  primaryButtonClass,
  secondaryButtonClass,
} from './studioUi'

interface QuestionEditorProps {
  packId: number
  saved: InterviewQuestion | null
  input: InterviewQuestionInput
  dirty: boolean
  expanded: boolean
  justDrafted: boolean
  topicsListId: string
  onToggle: () => void
  onChange: (input: InterviewQuestionInput) => void
  onDiscard: () => void
  onSaved: (question: InterviewQuestion) => void
  onRetired: () => void
}

export function QuestionEditor({
  packId,
  saved,
  input,
  dirty,
  expanded,
  justDrafted,
  topicsListId,
  onToggle,
  onChange,
  onDiscard,
  onSaved,
  onRetired,
}: QuestionEditorProps) {
  const queryClient = useQueryClient()

  const saveMutation = useMutation({
    mutationFn: (draft: InterviewQuestionInput) =>
      saved
        ? updateInterviewQuestion(saved.id, toQuestionPayload(draft))
        : createInterviewQuestion(packId, toQuestionPayload(draft)),
    onSuccess: async (question) => {
      await queryClient.invalidateQueries({ queryKey: ['interview'] })
      onSaved(question)
    },
  })

  const retireMutation = useMutation({
    mutationFn: retireInterviewQuestion,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['interview'] })
      onRetired()
    },
  })

  const errors = questionErrors(input)
  const warnings = questionWarnings(input)
  const keyPointCount = input.key_points.filter((keyPoint) => keyPoint.text.trim()).length
  const approvedCount = countApproved(input.key_points)
  const busy = saveMutation.isPending || retireMutation.isPending

  function handleRetire() {
    if (!saved) return
    const message = 'Retire this question and its follow-ups? It disappears from practice; past answers are kept.'
    if (window.confirm(message)) retireMutation.mutate(saved.id)
  }

  function handleDiscard() {
    const hasEdits = saved ? dirty : !!input.text.trim() || keyPointCount > 0
    const message = saved ? 'Discard unsaved changes to this question?' : 'Discard this new question?'
    if (!hasEdits || window.confirm(message)) onDiscard()
  }

  return (
    <div
      className={[
        'bg-card border rounded-xl',
        dirty ? 'border-amber-500/40' : justDrafted ? 'border-accent/40' : 'border-cardBorder',
      ].join(' ')}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="w-full flex items-start gap-3 p-4 text-left"
      >
        <div className="flex-1 min-w-0">
          <p className={`text-sm text-textPrimary leading-snug ${expanded ? '' : 'line-clamp-2'}`}>
            {input.text.trim() || <span className="text-textSecondary italic">Untitled question</span>}
          </p>
          <div className="flex flex-wrap items-center gap-1.5 mt-2">
            <span className="text-xs text-textSecondary mr-1">
              {plural(keyPointCount, 'key point')}, {approvedCount} approved, {plural(input.follow_ups.length, 'follow-up')}
              {saved ? `, ${plural(saved.answer_count, 'graded answer')}` : ''}
            </span>
            {!saved && <Badge tone="amber">Not saved yet</Badge>}
            {saved && dirty && <Badge tone="amber">Unsaved changes</Badge>}
            {justDrafted && <Badge tone="accent">Just drafted</Badge>}
            {approvedCount === 0 && <Badge tone="red">No approved key points</Badge>}
            {approvedCount > 0 && hasUnapprovedKeyPoints(input) && <Badge tone="amber">Needs review</Badge>}
          </div>
        </div>
        <ChevronIcon open={expanded} />
      </button>

      {expanded && (
        <fieldset disabled={busy} className="border-t border-cardBorder p-4 space-y-5 min-w-0">
          <div className="grid grid-cols-1 md:grid-cols-[1fr_10rem] gap-3">
            <Field label="Topic">
              <input
                type="text"
                list={topicsListId}
                maxLength={100}
                value={input.topic}
                onChange={(e) => onChange({ ...input, topic: e.target.value })}
                placeholder="e.g. Databases"
                className={inputClass}
              />
            </Field>
            <Field label="Answer time (seconds)">
              <input
                type="number"
                min={ANSWER_SECONDS_MIN}
                max={ANSWER_SECONDS_MAX}
                step={15}
                value={Number.isNaN(input.answer_seconds) ? '' : input.answer_seconds}
                onChange={(e) => onChange({ ...input, answer_seconds: e.target.valueAsNumber })}
                className={inputClass}
              />
            </Field>
          </div>

          <Field label="Question">
            <textarea
              rows={3}
              maxLength={2000}
              value={input.text}
              onChange={(e) => onChange({ ...input, text: e.target.value })}
              placeholder="What the interviewer asks"
              className={inputClass}
            />
          </Field>

          <KeyPointsEditor
            keyPoints={input.key_points}
            savedKeyPoints={saved?.key_points ?? []}
            onChange={(keyPoints) => onChange({ ...input, key_points: keyPoints })}
          />

          <MisconceptionsEditor
            misconceptions={input.misconceptions}
            onChange={(misconceptions) => onChange({ ...input, misconceptions })}
          />

          <FollowUpsEditor
            followUps={input.follow_ups}
            parentKeyPoints={input.key_points}
            savedFollowUps={saved?.follow_ups ?? []}
            onChange={(followUps) => onChange({ ...input, follow_ups: followUps })}
          />

          <IssueList tone="warning" issues={warnings} />
          <IssueList tone="error" issues={errors} />
          {saveMutation.isError && <Notice tone="error">Could not save: {apiErrorDetail(saveMutation.error)}</Notice>}
          {retireMutation.isError && (
            <Notice tone="error">Could not retire: {apiErrorDetail(retireMutation.error)}</Notice>
          )}

          <div className="flex flex-wrap items-center gap-2 pt-1">
            <button
              type="button"
              className={primaryButtonClass}
              disabled={!dirty || errors.length > 0}
              onClick={() => saveMutation.mutate(input)}
            >
              {saveMutation.isPending && <Spinner />}
              {saved ? 'Save question' : 'Create question'}
            </button>
            {(dirty || !saved) && (
              <button type="button" className={secondaryButtonClass} onClick={handleDiscard}>
                {saved ? 'Discard changes' : 'Discard'}
              </button>
            )}
            {saved && (
              <button type="button" className={`${dangerButtonClass} ml-auto`} onClick={handleRetire}>
                {retireMutation.isPending && <Spinner />}
                Retire
              </button>
            )}
          </div>
        </fieldset>
      )}
    </div>
  )
}
