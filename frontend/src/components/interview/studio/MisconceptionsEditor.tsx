import type { InterviewMisconceptionInput } from '../../../types/interview'
import { MISCONCEPTION_PENALTY } from '../utils'
import { MAX_MISCONCEPTIONS, newMisconceptionInput } from './studioModel'
import { PlusIcon, RemoveButton, inputClass, secondaryButtonClass } from './studioUi'

interface MisconceptionsEditorProps {
  misconceptions: InterviewMisconceptionInput[]
  onChange: (misconceptions: InterviewMisconceptionInput[]) => void
}

export function MisconceptionsEditor({ misconceptions, onChange }: MisconceptionsEditorProps) {
  function update(index: number, patch: Partial<InterviewMisconceptionInput>) {
    onChange(misconceptions.map((item, i) => (i === index ? { ...item, ...patch } : item)))
  }

  return (
    <section className="space-y-2">
      <div>
        <h4 className="text-sm font-semibold text-textPrimary">Misconceptions</h4>
        <p className="text-xs text-textSecondary">
          Wrong statements candidates often make. Stating one takes {MISCONCEPTION_PENALTY} points off the content score.
        </p>
      </div>

      {misconceptions.map((item, index) => (
        <div key={item.uid ?? index} className="rounded-lg border border-red-500/20 bg-red-500/5 p-3 space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-textSecondary">#{index + 1}</span>
            <span className="ml-auto">
              <RemoveButton
                label="Remove misconception"
                onClick={() => onChange(misconceptions.filter((_, i) => i !== index))}
              />
            </span>
          </div>
          <textarea
            rows={2}
            maxLength={1000}
            value={item.text}
            onChange={(e) => update(index, { text: e.target.value })}
            placeholder="Wrong statement, e.g. Adding more indexes always makes queries faster"
            aria-label={`Misconception ${index + 1} statement`}
            className={inputClass}
          />
          <textarea
            rows={2}
            maxLength={1000}
            value={item.correction}
            onChange={(e) => update(index, { correction: e.target.value })}
            placeholder="Correction shown to the candidate"
            aria-label={`Misconception ${index + 1} correction`}
            className={inputClass}
          />
        </div>
      ))}

      <button
        type="button"
        className={secondaryButtonClass}
        disabled={misconceptions.length >= MAX_MISCONCEPTIONS}
        onClick={() => onChange([...misconceptions, newMisconceptionInput()])}
      >
        <PlusIcon /> Add misconception
      </button>
    </section>
  )
}
