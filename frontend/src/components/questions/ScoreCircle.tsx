import { scoreColor } from './utils'

export function ScoreCircle({
  score,
  size = 'lg',
}: {
  score: number | null
  size?: 'sm' | 'lg'
}) {
  if (score === null) return null
  const c = scoreColor(score)
  const dim = size === 'lg' ? 'w-14 h-14 text-xl border-[3px]' : 'w-10 h-10 text-sm border-2'

  return (
    <div
      className={`${dim} rounded-full ${c.ring} ${c.glow} flex items-center justify-center font-bold ${c.text}`}
    >
      {score.toFixed(1)}
    </div>
  )
}
