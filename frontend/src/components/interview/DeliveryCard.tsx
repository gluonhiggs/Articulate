import type { InterviewDelivery } from '../../types/interview'
import { DeliveryMeters } from './DeliveryMeters'
import { MIN_DELIVERY_WORDS, firstSentence, plural } from './utils'

export function deliverySummary(delivery: InterviewDelivery): string {
  const parts = [`${delivery.words} words in ${Math.round(delivery.speaking_seconds)}s`]
  if (delivery.words_per_minute !== null) parts.push(`${Math.round(delivery.words_per_minute)} wpm`)
  if (delivery.long_pauses > 0) parts.push(plural(delivery.long_pauses, 'long pause'))
  if (delivery.grammar_available && delivery.grammar_issues.length > 0) {
    parts.push(plural(delivery.grammar_issues.length, 'grammar note'))
  }
  return parts.join(' · ')
}

export function DeliveryDetails({ delivery }: { delivery: InterviewDelivery }) {
  return (
    <div className="space-y-3">
      {delivery.score === null && (
        <p className="text-amber-400 text-xs">Too short to score delivery (fewer than {MIN_DELIVERY_WORDS} words).</p>
      )}

      <DeliveryMeters delivery={delivery} />

      {delivery.grammar_available && delivery.grammar_issues.length > 0 && (
        <ul className="space-y-1.5 pt-1">
          {delivery.grammar_issues.map((issue, i) => (
            <li key={i} className="text-sm flex flex-wrap items-baseline gap-x-2" title={issue.message}>
              <span className="correction-wrong">{issue.text}</span>
              {issue.replacements.length > 0 && (
                <span className="correction-right">{issue.replacements.slice(0, 3).join(' / ')}</span>
              )}
              <span className="text-xs text-textSecondary">{firstSentence(issue.message)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
