import type { InterviewKeyPoint, InterviewKeyPointInput } from '../../../types/interview'
import {
  MAX_KEY_POINTS,
  WEIGHT_OPTIONS,
  approveAllKeyPoints,
  newKeyPointInput,
  quoteStatus,
  type KeyPointWeight,
} from './studioModel'
import { PlusIcon, QuoteBadge, RemoveButton, Toggle, inputClass, secondaryButtonClass, selectClass } from './studioUi'

interface KeyPointsEditorProps {
  keyPoints: InterviewKeyPointInput[]
  savedKeyPoints: InterviewKeyPoint[]
  onChange: (keyPoints: InterviewKeyPointInput[]) => void
}

export function KeyPointsEditor({ keyPoints, savedKeyPoints, onChange }: KeyPointsEditorProps) {
  const savedByUid = new Map(savedKeyPoints.map((keyPoint) => [keyPoint.uid, keyPoint]))
  const hasUnapproved = keyPoints.some((keyPoint) => keyPoint.text.trim() && !keyPoint.approved)

  function update(index: number, patch: Partial<InterviewKeyPointInput>) {
    onChange(keyPoints.map((keyPoint, i) => (i === index ? { ...keyPoint, ...patch } : keyPoint)))
  }

  return (
    <section className="space-y-2">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-textPrimary">Key points</h4>
          <p className="text-xs text-textSecondary">
            Atomic facts a correct answer must contain. Only approved key points are graded.
          </p>
        </div>
        {hasUnapproved && (
          <button type="button" className={secondaryButtonClass} onClick={() => onChange(approveAllKeyPoints(keyPoints))}>
            Approve all
          </button>
        )}
      </div>

      {keyPoints.map((keyPoint, index) => (
        <div
          key={keyPoint.uid ?? index}
          className={[
            'rounded-lg border p-3 space-y-2',
            keyPoint.approved ? 'border-cardBorder bg-background/40' : 'border-amber-500/30 bg-amber-500/5',
          ].join(' ')}
        >
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-xs font-mono text-textSecondary">#{index + 1}</span>
            <select
              value={keyPoint.weight}
              onChange={(e) => update(index, { weight: Number(e.target.value) as KeyPointWeight })}
              className={selectClass}
              aria-label="Weight"
            >
              {WEIGHT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label} ({option.value})
                </option>
              ))}
            </select>
            <Toggle
              checked={keyPoint.approved}
              onChange={(approved) => update(index, { approved })}
              label={keyPoint.approved ? 'Approved' : 'Not approved'}
            />
            <QuoteBadge status={quoteStatus(keyPoint, savedByUid.get(keyPoint.uid ?? ''))} />
            <span className="ml-auto">
              <RemoveButton label="Remove key point" onClick={() => onChange(keyPoints.filter((_, i) => i !== index))} />
            </span>
          </div>
          <textarea
            rows={2}
            maxLength={1000}
            value={keyPoint.text}
            onChange={(e) => update(index, { text: e.target.value })}
            placeholder="e.g. An index speeds up reads but slows down writes"
            aria-label={`Key point ${index + 1} text`}
            className={inputClass}
          />
          <input
            type="text"
            maxLength={2000}
            value={keyPoint.source_quote ?? ''}
            onChange={(e) => update(index, { source_quote: e.target.value })}
            placeholder="Source quote (optional, copied verbatim from a source)"
            aria-label={`Key point ${index + 1} source quote`}
            className={`${inputClass} text-xs`}
          />
        </div>
      ))}

      <button
        type="button"
        className={secondaryButtonClass}
        disabled={keyPoints.length >= MAX_KEY_POINTS}
        onClick={() => onChange([...keyPoints, newKeyPointInput()])}
      >
        <PlusIcon /> Add key point
      </button>
    </section>
  )
}
