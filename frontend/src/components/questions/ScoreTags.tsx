import type { Attempt } from '../../types'
import { tagClass } from './utils'

export function ScoreTags({
  attempt,
  onPronunDetails,
}: {
  attempt: Attempt
  onPronunDetails?: () => void
}) {
  const tags: { label: string; value: number | null; key: string }[] = [
    { label: 'Fluency', value: attempt.fluency, key: 'f' },
    { label: 'Vocab', value: attempt.vocabulary, key: 'v' },
    { label: 'Grammar', value: attempt.grammar, key: 'g' },
    { label: 'Pronun', value: attempt.pronunciation, key: 'p' },
  ]

  return (
    <div className="flex flex-wrap gap-2">
      {tags.map((t) => {
        if (t.value === null) return null
        const isPronun = t.key === 'p'
        return (
          <span key={t.key} className="inline-flex items-center gap-1">
            <span className={`px-3 py-1 rounded-full text-xs font-medium ${tagClass(t.value)}`}>
              {t.label}: {t.value.toFixed(1)}
            </span>
            {isPronun && onPronunDetails && (
              <button
                onClick={onPronunDetails}
                className="text-[11px] text-gray-400 hover:text-teal-400 transition-colors underline underline-offset-2"
              >
                Details
              </button>
            )}
          </span>
        )
      })}
    </div>
  )
}
