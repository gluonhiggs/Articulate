import type { InterviewFollowUpInput, InterviewKeyPointInput, InterviewQuestion } from '../../../types/interview'
import { KeyPointsEditor } from './KeyPointsEditor'
import { MisconceptionsEditor } from './MisconceptionsEditor'
import {
  ANSWER_SECONDS_MAX,
  ANSWER_SECONDS_MIN,
  MAX_FOLLOW_UPS,
  keyPointOptionLabel,
  newFollowUpInput,
  plural,
} from './studioModel'
import { Field, PlusIcon, RemoveButton, inputClass, secondaryButtonClass } from './studioUi'

interface FollowUpsEditorProps {
  followUps: InterviewFollowUpInput[]
  parentKeyPoints: InterviewKeyPointInput[]
  savedFollowUps: InterviewQuestion[]
  onChange: (followUps: InterviewFollowUpInput[]) => void
}

export function FollowUpsEditor({ followUps, parentKeyPoints, savedFollowUps, onChange }: FollowUpsEditorProps) {
  const triggerOptions = parentKeyPoints.flatMap((keyPoint, index) =>
    keyPoint.uid && keyPoint.text.trim() ? [{ uid: keyPoint.uid, label: keyPointOptionLabel(keyPoint, index) }] : [],
  )

  function update(index: number, patch: Partial<InterviewFollowUpInput>) {
    onChange(followUps.map((followUp, i) => (i === index ? { ...followUp, ...patch } : followUp)))
  }

  return (
    <section className="space-y-3">
      <div>
        <h4 className="text-sm font-semibold text-textPrimary">Follow-up questions</h4>
        <p className="text-xs text-textSecondary">
          Asked when the trigger key point is missing, partial or incorrect. A follow-up without a trigger is asked
          after a strong answer. Removed follow-ups are retired when you save.
        </p>
      </div>

      {followUps.map((followUp, index) => {
        const saved = savedFollowUps.find((item) => item.uid === followUp.uid)
        const triggerValue = triggerOptions.some((option) => option.uid === followUp.trigger_key_point_uid)
          ? (followUp.trigger_key_point_uid ?? '')
          : ''
        return (
          <div key={followUp.uid ?? index} className="rounded-xl border border-cardBorder bg-background/40 p-4 space-y-4">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-textSecondary">
                Follow-up {index + 1}
              </span>
              {saved && saved.answer_count > 0 && (
                <span className="text-xs text-gray-500">{plural(saved.answer_count, 'graded answer')}</span>
              )}
              <span className="ml-auto">
                <RemoveButton
                  label="Remove follow-up"
                  onClick={() => onChange(followUps.filter((_, i) => i !== index))}
                />
              </span>
            </div>

            <textarea
              rows={2}
              maxLength={2000}
              value={followUp.text}
              onChange={(e) => update(index, { text: e.target.value })}
              placeholder="Follow-up question text"
              aria-label={`Follow-up ${index + 1} question text`}
              className={inputClass}
            />

            <div className="grid grid-cols-1 md:grid-cols-[1fr_10rem] gap-3">
              <Field label="Trigger key point">
                <select
                  value={triggerValue}
                  onChange={(e) => update(index, { trigger_key_point_uid: e.target.value || null })}
                  className={inputClass}
                >
                  <option value="">No trigger (after a strong answer)</option>
                  {triggerOptions.map((option) => (
                    <option key={option.uid} value={option.uid}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Answer time (seconds)">
                <input
                  type="number"
                  min={ANSWER_SECONDS_MIN}
                  max={ANSWER_SECONDS_MAX}
                  step={15}
                  value={Number.isNaN(followUp.answer_seconds) ? '' : followUp.answer_seconds}
                  onChange={(e) => update(index, { answer_seconds: e.target.valueAsNumber })}
                  className={inputClass}
                />
              </Field>
            </div>

            <KeyPointsEditor
              keyPoints={followUp.key_points}
              savedKeyPoints={saved?.key_points ?? []}
              onChange={(keyPoints) => update(index, { key_points: keyPoints })}
            />
            <MisconceptionsEditor
              misconceptions={followUp.misconceptions}
              onChange={(misconceptions) => update(index, { misconceptions })}
            />
          </div>
        )
      })}

      <button
        type="button"
        className={secondaryButtonClass}
        disabled={followUps.length >= MAX_FOLLOW_UPS}
        onClick={() => onChange([...followUps, newFollowUpInput()])}
      >
        <PlusIcon /> Add follow-up
      </button>
    </section>
  )
}
