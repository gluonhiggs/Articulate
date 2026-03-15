interface StreakCardProps {
  currentStreak: number
  longestStreak: number
  totalAttempts: number
}

export function StreakCard({ currentStreak, longestStreak, totalAttempts }: StreakCardProps) {
  return (
    <div className="bg-card border border-cardBorder rounded-xl p-5">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-baseline gap-2">
            <span className="text-5xl font-bold text-textPrimary">{currentStreak}</span>
            <span className="text-2xl">🔥</span>
          </div>
          <p className="text-textSecondary text-sm mt-1">Day streak</p>
        </div>

        <div className="text-right">
          <p className="text-xs text-textSecondary">Longest</p>
          <p className="text-lg font-semibold text-textPrimary">{longestStreak}</p>
        </div>
      </div>

      <div className="mt-4 pt-4 border-t border-cardBorder">
        <p className="text-xs text-textSecondary">Today's goal</p>
        <p className="text-sm text-accent font-medium mt-0.5">Record 25 answers today</p>
        <div className="mt-2 bg-background rounded-full h-1.5 overflow-hidden">
          <div
            className="bg-gradient-to-r from-cyan-500 to-purple-600 h-full rounded-full transition-all duration-500"
            style={{ width: `${Math.min(100, (totalAttempts / 25) * 100)}%` }}
          />
        </div>
        <p className="text-xs text-textSecondary mt-1">{totalAttempts} / 25 today</p>
      </div>
    </div>
  )
}
