import type { ContentBand } from '../../types/interview'
import { bandStyle } from './utils'

const RADIUS = 42
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

export function ScoreRing({ score, band }: { score: number | null; band: ContentBand | null }) {
  const style = bandStyle(band)
  const progress = score === null ? 0 : Math.min(100, Math.max(0, score)) / 100

  return (
    <div className="relative w-24 h-24 shrink-0">
      <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
        <circle cx="50" cy="50" r={RADIUS} fill="none" stroke="#1E293B" strokeWidth="8" />
        <circle
          cx="50"
          cy="50"
          r={RADIUS}
          fill="none"
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={CIRCUMFERENCE * (1 - progress)}
          className={`${style.stroke} transition-all duration-700 ease-out`}
        />
      </svg>
      <span className={`absolute inset-0 flex items-center justify-center font-bold text-2xl ${style.text}`}>
        {score === null ? '--' : score}
      </span>
    </div>
  )
}
