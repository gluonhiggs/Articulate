import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchForecast } from '../api/client'
import type { ForecastEntry } from '../types'

export function Forecast() {
  const { data: forecast, isLoading, isError } = useQuery<ForecastEntry[]>({
    queryKey: ['forecast'],
    queryFn: fetchForecast,
    staleTime: 5 * 60 * 1000,
  })

  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-xl font-semibold text-textPrimary mb-1">Test Forecast</h1>
      <p className="text-sm text-textSecondary mb-6">
        Topics that have appeared in recent IELTS tests, sorted by recency. Practice high-probability topics first.
      </p>

      {isLoading && (
        <div className="flex items-center gap-2 text-textSecondary text-sm">
          <div className="animate-spin h-4 w-4 border-2 border-teal-400 border-t-transparent rounded-full" />
          Loading forecast...
        </div>
      )}

      {isError && (
        <div className="rounded-lg bg-red-500/10 border border-red-500/20 p-3">
          <p className="text-red-400 text-sm">Could not load forecast data. Check that the backend is running.</p>
        </div>
      )}

      {forecast && forecast.length === 0 && (
        <div className="bg-card/50 border border-dashed border-white/10 rounded-xl p-8 text-center">
          <p className="text-gray-400 text-sm">No forecast data available.</p>
          <p className="text-gray-500 text-xs mt-1">Questions need topic tags to appear here.</p>
        </div>
      )}

      {forecast && forecast.length > 0 && (
        <div className="space-y-2">
          {forecast.map((entry, i) => (
            <div
              key={entry.topic_tag}
              className="flex items-center gap-3 bg-card border border-cardBorder rounded-xl px-4 py-3"
            >
              <span className="text-textSecondary text-sm font-mono w-5 shrink-0">{i + 1}</span>
              <div className="flex-1 min-w-0">
                <span className="text-textPrimary font-medium capitalize">
                  {entry.topic_tag.replace(/_/g, ' ')}
                </span>
                <span className="ml-2 text-xs text-textSecondary">
                  {entry.count} question{entry.count !== 1 ? 's' : ''}
                </span>
              </div>
              {entry.last_seen_date && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-teal-500/10 text-teal-400 border border-teal-500/20 shrink-0">
                  last seen {entry.last_seen_date}
                </span>
              )}
              <Link
                to="/practice/part1"
                className="text-xs px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-gray-300 hover:bg-white/10 transition-colors shrink-0"
              >
                Practice now
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
