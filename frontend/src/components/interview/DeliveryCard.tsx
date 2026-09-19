import type { InterviewDelivery } from '../../types/interview'
import { MIN_DELIVERY_WORDS } from './utils'

function Metric({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="bg-background rounded-lg px-3 py-2.5">
      <p className="text-[11px] text-textSecondary">{label}</p>
      <p className="text-textPrimary font-semibold text-sm mt-0.5">{value}</p>
      <p className="text-[11px] text-gray-500 mt-0.5">{hint}</p>
    </div>
  )
}

function formatRate(value: number | null, digits = 1): string {
  return value === null ? '--' : value.toFixed(digits)
}

export function DeliveryCard({ delivery }: { delivery: InterviewDelivery }) {
  return (
    <div className="bg-card border border-cardBorder rounded-xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-textPrimary font-semibold text-sm">English delivery details</p>
        <p className="text-textSecondary text-xs">
          {delivery.words} words in {Math.round(delivery.speaking_seconds)}s
        </p>
      </div>

      {delivery.score === null && (
        <p className="text-amber-400 text-xs">Too short to score delivery (fewer than {MIN_DELIVERY_WORDS} words).</p>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <Metric
          label="Speaking rate"
          value={delivery.words_per_minute === null ? '--' : `${Math.round(delivery.words_per_minute)} wpm`}
          hint="Comfortable: 120-170"
        />
        <Metric
          label="Long pauses"
          value={`${formatRate(delivery.pauses_per_100_words)} / 100 words`}
          hint={`${delivery.long_pauses} in total; aim for 3 or fewer`}
        />
        <Metric
          label="Grammar errors"
          value={delivery.grammar_available ? `${formatRate(delivery.grammar_errors_per_100_words)} / 100 words` : 'Unavailable'}
          hint={delivery.grammar_available ? 'Aim for 2 or fewer' : 'Grammar check unavailable'}
        />
        <Metric
          label="Lexical diversity"
          value={delivery.lexical_diversity === null ? '--' : delivery.lexical_diversity.toFixed(0)}
          hint={delivery.lexical_diversity === null ? 'Needs 50+ words' : 'MTLD; 80+ is varied'}
        />
      </div>

      {delivery.grammar_available && delivery.grammar_issues.length > 0 && (
        <div>
          <p className="text-xs text-textSecondary mb-2">Grammar issues</p>
          <ul className="space-y-1.5">
            {delivery.grammar_issues.map((issue, i) => (
              <li key={i} className="text-sm text-gray-300 flex flex-wrap items-baseline gap-x-2">
                <span className="correction-wrong">{issue.text}</span>
                {issue.replacements.length > 0 && (
                  <span className="correction-right">{issue.replacements.slice(0, 3).join(' / ')}</span>
                )}
                <span className="text-xs text-textSecondary">{issue.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
