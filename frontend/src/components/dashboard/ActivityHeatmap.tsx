import CalendarHeatmap from 'react-calendar-heatmap'
import type { ReactCalendarHeatmapValue } from 'react-calendar-heatmap'
import 'react-calendar-heatmap/dist/styles.css'
import type { HeatmapEntry } from '../../types'

interface ActivityHeatmapProps {
  values: HeatmapEntry[]
}

// Extend the library's value type with our extra fields
interface HeatmapValue extends ReactCalendarHeatmapValue<string> {
  count: number
  intensity: number
}

export function ActivityHeatmap({ values }: ActivityHeatmapProps) {
  const today = new Date()
  const startDate = new Date(today)
  startDate.setMonth(startDate.getMonth() - 5)

  const heatmapValues: HeatmapValue[] = values.map((v) => ({
    date: v.date,
    count: v.count,
    intensity: v.intensity,
  }))

  function classForValue(value: ReactCalendarHeatmapValue<string> | undefined): string {
    const v = value as HeatmapValue | undefined
    if (!v || !v.count || v.count === 0) return 'color-empty'
    if (v.intensity >= 4) return 'color-scale-4'
    if (v.intensity >= 3) return 'color-scale-3'
    if (v.intensity >= 2) return 'color-scale-2'
    return 'color-scale-1'
  }

  function titleForValue(value: ReactCalendarHeatmapValue<string> | undefined): string {
    const v = value as HeatmapValue | undefined
    if (!v || !v.count || v.count === 0) return 'No activity'
    return `${v.date}: ${v.count} attempt${v.count !== 1 ? 's' : ''}`
  }

  return (
    <div className="w-full">
      <CalendarHeatmap
        startDate={startDate}
        endDate={today}
        values={heatmapValues}
        classForValue={classForValue}
        titleForValue={titleForValue}
        showWeekdayLabels={true}
        gutterSize={3}
      />
    </div>
  )
}
