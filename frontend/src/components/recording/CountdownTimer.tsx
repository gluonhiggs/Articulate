interface CountdownTimerProps {
  seconds: number
  maxSeconds: number
}

export function CountdownTimer({ seconds, maxSeconds }: CountdownTimerProps) {
  const radius = 20
  const circumference = 2 * Math.PI * radius
  const progress = maxSeconds > 0 ? seconds / maxSeconds : 0
  const strokeDashoffset = circumference * (1 - progress)

  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width="56" height="56" viewBox="0 0 56 56" className="-rotate-90">
        {/* Background circle */}
        <circle
          cx="28"
          cy="28"
          r={radius}
          fill="none"
          stroke="#1E293B"
          strokeWidth="3"
        />
        {/* Progress circle */}
        <circle
          cx="28"
          cy="28"
          r={radius}
          fill="none"
          stroke="#06B6D4"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          className="transition-all duration-1000 ease-linear"
        />
      </svg>
      <span className="absolute text-xs font-semibold text-accent">
        {minutes > 0 ? `${minutes}:${secs.toString().padStart(2, '0')}` : `${secs}s`}
      </span>
    </div>
  )
}
