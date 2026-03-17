import { useMemo } from 'react'
import type { HeatmapEntry } from '../../types'

interface ActivityHeatmapProps {
  values: HeatmapEntry[]
}

const CELL_SIZE = 12
const GAP = 3
const COLORS = [
  '#161b22',                    // 0: empty
  'rgba(6, 182, 212, 0.15)',    // 1: low
  'rgba(6, 182, 212, 0.40)',    // 2: medium
  'rgba(6, 182, 212, 0.70)',    // 3: high
  '#06b6d4',                    // 4: max
]

function getColor(intensity: number): string {
  return COLORS[Math.min(intensity, 4)] ?? COLORS[0]
}

export function ActivityHeatmap({ values }: ActivityHeatmapProps) {
  const { weeks, monthLabels } = useMemo(() => {
    // Build a date → entry lookup
    const lookup = new Map<string, HeatmapEntry>()
    for (const v of values) lookup.set(v.date, v)

    const today = new Date()
    // Start from 180 days ago, aligned to start of that week (Sunday)
    const startRaw = new Date(today)
    startRaw.setDate(startRaw.getDate() - 179)
    const start = new Date(startRaw)
    start.setDate(start.getDate() - start.getDay()) // back to Sunday

    const weeks: { date: Date; entry: HeatmapEntry | null }[][] = []
    const monthLabels: { label: string; col: number }[] = []

    let current = new Date(start)
    let lastMonth = -1

    while (current <= today || weeks.length === 0 || weeks[weeks.length - 1].length < 7) {
      const dayOfWeek = current.getDay()
      if (dayOfWeek === 0) weeks.push([])

      const dateStr = current.toISOString().slice(0, 10)
      const entry = lookup.get(dateStr) ?? null
      const week = weeks[weeks.length - 1]
      const isFuture = current > today
      week.push({ date: new Date(current), entry: isFuture ? null : entry })

      // Track month labels
      if (current.getMonth() !== lastMonth && dayOfWeek === 0 && !isFuture) {
        lastMonth = current.getMonth()
        monthLabels.push({
          label: current.toLocaleString('en-US', { month: 'short' }),
          col: weeks.length - 1,
        })
      }

      current.setDate(current.getDate() + 1)
      if (weeks.length > 52) break
    }

    return { weeks, monthLabels }
  }, [values])

  const totalWidth = weeks.length * (CELL_SIZE + GAP)

  return (
    <div className="w-full overflow-x-auto">
      {/* Month labels */}
      <div className="relative mb-1" style={{ height: 16, width: totalWidth }}>
        {monthLabels.map((m, i) => (
          <span
            key={i}
            className="absolute text-[10px] text-textSecondary"
            style={{ left: m.col * (CELL_SIZE + GAP) }}
          >
            {m.label}
          </span>
        ))}
      </div>

      {/* Grid */}
      <div className="flex gap-[3px]">
        {weeks.map((week, wi) => (
          <div key={wi} className="flex flex-col gap-[3px]">
            {week.map((day, di) => {
              const intensity = day.entry?.intensity ?? 0
              const count = day.entry?.count ?? 0
              const dateStr = day.date.toISOString().slice(0, 10)
              return (
                <div
                  key={di}
                  className="rounded-[2px] transition-colors"
                  style={{
                    width: CELL_SIZE,
                    height: CELL_SIZE,
                    backgroundColor: day.entry === null && count === 0
                      ? COLORS[0]
                      : getColor(intensity),
                  }}
                  title={count > 0 ? `${dateStr}: ${count} attempt${count !== 1 ? 's' : ''}` : `${dateStr}: No activity`}
                />
              )
            })}
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="flex items-center justify-end gap-1.5 mt-2">
        <span className="text-[10px] text-textSecondary mr-1">Less</span>
        {COLORS.map((color, i) => (
          <div
            key={i}
            className="rounded-[2px]"
            style={{ width: 10, height: 10, backgroundColor: color }}
          />
        ))}
        <span className="text-[10px] text-textSecondary ml-1">More</span>
      </div>
    </div>
  )
}
