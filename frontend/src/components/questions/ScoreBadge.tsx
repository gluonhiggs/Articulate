import { scoreGradient } from './utils'

interface ScoreBadgeProps {
  score: number | null
  size?: 'sm' | 'md' | 'lg'
}

const sizeClasses = {
  sm: 'w-8 h-8 text-xs',
  md: 'w-10 h-10 text-sm',
  lg: 'w-14 h-14 text-base',
}

export function ScoreBadge({ score, size = 'md' }: ScoreBadgeProps) {
  const sizeClass = sizeClasses[size]

  if (score === null) {
    return (
      <div
        className={`${sizeClass} rounded-full border-2 border-cardBorder flex items-center justify-center`}
      >
        <span className="text-textSecondary text-xs">-</span>
      </div>
    )
  }

  return (
    <div
      className={`${sizeClass} rounded-full ${scoreGradient(score)} flex items-center justify-center font-semibold shadow-lg`}
      title={`Band ${score}`}
    >
      {score % 1 === 0 ? score.toFixed(0) : score.toFixed(1)}
    </div>
  )
}
