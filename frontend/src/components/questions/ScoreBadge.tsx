interface ScoreBadgeProps {
  score: number | null
  size?: 'sm' | 'md' | 'lg'
}

function getScoreStyle(score: number): string {
  if (score >= 7) {
    return 'bg-gradient-to-br from-cyan-500 to-cyan-400 text-white'
  }
  if (score >= 6) {
    return 'bg-gradient-to-br from-purple-500 to-purple-400 text-white'
  }
  if (score >= 5.5) {
    return 'bg-gradient-to-br from-yellow-500 to-yellow-400 text-white'
  }
  return 'bg-gradient-to-br from-red-600 to-red-500 text-white'
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
        <span className="text-textSecondary text-xs">—</span>
      </div>
    )
  }

  return (
    <div
      className={`${sizeClass} rounded-full ${getScoreStyle(score)} flex items-center justify-center font-semibold shadow-lg`}
      title={`Band ${score}`}
    >
      {score % 1 === 0 ? score.toFixed(0) : score.toFixed(1)}
    </div>
  )
}
