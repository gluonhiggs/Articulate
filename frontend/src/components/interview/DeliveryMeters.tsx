import type { InterviewDelivery } from '../../types/interview'

type Severity = 'good' | 'warning' | 'critical' | 'unknown'

/**
 * Each metric is a ratio against its own target, so the form is a meter list: a name,
 * a track with the target zone drawn on it, and a figure. The zone replaces the hint
 * sentence the tiles used to carry - where the fill lands against it IS the hint.
 *
 * `zone` and `warn` are kept in step with the scoring anchors in
 * backend/services/interview_delivery.py, so the colour here cannot contradict the
 * delivery score computed there.
 */
interface MeterSpec {
  name: string
  value: number | null
  figure: string
  max: number
  zone: [number, number]
  warn: [number, number]
  target: string
  below: string
  above: string
  inside: string
  // Shown on hover: what the figure measures, for a metric whose unit is not obvious.
  hint: string
}

const BAR = {
  good: 'bg-teal-400',
  warning: 'bg-yellow-400',
  critical: 'bg-red-400',
  unknown: 'bg-gray-600',
} as const

const WORD = {
  good: 'text-teal-400',
  warning: 'text-yellow-400',
  critical: 'text-red-400',
  unknown: 'text-gray-500',
} as const

function severity(spec: MeterSpec): Severity {
  if (spec.value === null) return 'unknown'
  if (spec.value >= spec.zone[0] && spec.value <= spec.zone[1]) return 'good'
  if (spec.value >= spec.warn[0] && spec.value <= spec.warn[1]) return 'warning'
  return 'critical'
}

function stateWord(spec: MeterSpec): string {
  if (spec.value === null) return 'not measured'
  if (spec.value < spec.zone[0]) return spec.below
  if (spec.value > spec.zone[1]) return spec.above
  return spec.inside
}

function percent(value: number, max: number): number {
  return Math.min(100, Math.max(0, (value / max) * 100))
}

function Meter({ spec }: { spec: MeterSpec }) {
  const state = severity(spec)
  const zoneStart = percent(spec.zone[0], spec.max)
  const zoneEnd = percent(spec.zone[1], spec.max)
  const filled = spec.value === null ? 0 : percent(spec.value, spec.max)

  return (
    <div className="bg-background rounded-lg px-3.5 py-3" title={spec.hint}>
      <div className="flex items-baseline gap-2">
        <span className="text-[11px] text-textSecondary truncate">{spec.name}</span>
        <span className="ml-auto text-sm font-semibold text-textPrimary shrink-0">{spec.figure}</span>
      </div>

      <div className="relative h-2 mt-2.5 rounded-full bg-white/[0.06] overflow-hidden">
        <div
          className="absolute inset-y-0 bg-white/[0.07]"
          style={{ left: `${zoneStart}%`, width: `${Math.max(0, zoneEnd - zoneStart)}%` }}
        />
        {spec.value !== null && filled > 0 && (
          <div
            className={`absolute inset-y-0 left-0 rounded-full ${BAR[state]}`}
            style={{ width: `${Math.max(1.5, filled)}%` }}
          />
        )}
        {/* Drawn last so the target boundaries stay readable through the fill. */}
        {[zoneStart, zoneEnd].map((at, i) =>
          at > 0 && at < 100 ? (
            <div key={i} className="absolute inset-y-0 w-px bg-white/40" style={{ left: `${at}%` }} />
          ) : null,
        )}
      </div>

      <div className="flex items-baseline gap-2 mt-1.5">
        <span className={`text-[10px] font-medium ${WORD[state]}`}>{stateWord(spec)}</span>
        <span className="ml-auto text-[10px] text-gray-500 shrink-0">{spec.target}</span>
      </div>
    </div>
  )
}

export function deliveryMeterSpecs(delivery: InterviewDelivery): MeterSpec[] {
  const { words_per_minute, pauses_per_100_words, grammar_errors_per_100_words, lexical_diversity } = delivery
  return [
    {
      name: 'Speaking rate',
      value: words_per_minute,
      figure: words_per_minute === null ? '--' : `${Math.round(words_per_minute)} wpm`,
      max: 240,
      zone: [120, 170],
      warn: [90, 210],
      target: '120-170',
      below: 'too slow',
      above: 'too fast',
      inside: 'comfortable',
      hint: 'Words per minute while actually talking, with long pauses taken out.',
    },
    {
      name: 'Long pauses',
      value: pauses_per_100_words,
      figure: pauses_per_100_words === null ? '--' : `${pauses_per_100_words.toFixed(1)} / 100 words`,
      max: 12,
      zone: [0, 3],
      warn: [0, 8],
      target: 'up to 3',
      below: 'few',
      above: 'too many',
      inside: 'few',
      hint: 'Silences long enough to sound like hesitation, counted per 100 words spoken.',
    },
    {
      name: 'Grammar errors',
      value: delivery.grammar_available ? grammar_errors_per_100_words : null,
      figure:
        !delivery.grammar_available || grammar_errors_per_100_words === null
          ? 'not checked'
          : `${grammar_errors_per_100_words.toFixed(1)} / 100 words`,
      max: 8,
      zone: [0, 2],
      warn: [0, 5],
      target: 'up to 2',
      below: 'clean',
      above: 'above target',
      inside: 'clean',
      hint: 'Real grammar mistakes only. Dialect preferences and style advice do not count.',
    },
    {
      name: 'Word variety',
      value: lexical_diversity,
      figure: lexical_diversity === null ? '--' : lexical_diversity.toFixed(0),
      max: 100,
      zone: [80, 100],
      warn: [50, 100],
      target: 'aim 80+',
      below: 'repeats early',
      above: 'varied',
      inside: 'varied',
      hint: 'How many words you speak, on average, before you start reusing the same ones.',
    },
  ]
}

export function DeliveryMeters({ delivery }: { delivery: InterviewDelivery }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
      {deliveryMeterSpecs(delivery).map((spec) => (
        <Meter key={spec.name} spec={spec} />
      ))}
    </div>
  )
}
