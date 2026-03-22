import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchDashboard } from '../api/client'
import { ActivityHeatmap } from '../components/dashboard/ActivityHeatmap'
import { StreakCard } from '../components/dashboard/StreakCard'
import type { DashboardData } from '../types'

function PartLaunchButton({
  part,
  label,
  description,
  to,
  color,
}: {
  part: string
  label: string
  description: string
  to: string
  color: string
}) {
  return (
    <Link
      to={to}
      className={`block bg-card border border-cardBorder rounded-xl p-4 hover:border-accent/40 hover:shadow-lg hover:shadow-accent/5 hover:-translate-y-0.5 transition-all duration-200`}
    >
      <div className={`w-10 h-10 rounded-lg ${color} flex items-center justify-center mb-3`}>
        <span className="text-white font-bold text-sm">{part}</span>
      </div>
      <p className="text-textPrimary font-semibold text-sm">{label}</p>
      <p className="text-textSecondary text-xs mt-1">{description}</p>
    </Link>
  )
}

function BandDisplay({ band }: { band: number | null }) {
  if (band === null) {
    return (
      <div className="bg-card border border-cardBorder rounded-xl p-5 flex flex-col items-center justify-center text-center">
        <div className="w-20 h-20 rounded-full border-4 border-cardBorder flex items-center justify-center mb-3">
          <span className="text-textSecondary text-2xl font-bold">?</span>
        </div>
        <p className="text-textSecondary text-sm">No data yet</p>
        <p className="text-xs text-textSecondary mt-1">Practice more to see your band score</p>
      </div>
    )
  }

  return (
    <div className="bg-card border border-cardBorder rounded-xl p-5 flex flex-col items-center justify-center text-center">
      <div className="w-20 h-20 rounded-full bg-gradient-to-br from-cyan-500 to-purple-600 flex items-center justify-center mb-3 shadow-lg shadow-cyan-500/20">
        <span className="text-white text-2xl font-bold">{band.toFixed(1)}</span>
      </div>
      <p className="text-textPrimary font-semibold text-sm">Estimated Band</p>
      <p className="text-xs text-textSecondary mt-1">Based on recent attempts</p>
    </div>
  )
}

function SkeletonBlock({ className }: { className?: string }) {
  return <div className={`bg-card animate-pulse rounded-xl ${className ?? ''}`} />
}

export function Home() {
  const { data, isLoading, isError, error } = useQuery<DashboardData>({
    queryKey: ['dashboard'],
    queryFn: fetchDashboard,
    staleTime: 60 * 1000,
  })

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-textPrimary">Dashboard</h1>
        <p className="text-textSecondary text-sm mt-1">Your IELTS Speaking practice progress</p>
      </div>

      {isError && (
        <div className="bg-red-900/20 border border-red-500/30 rounded-xl p-4 mb-6">
          <p className="text-red-400 text-sm font-medium">Backend not responding</p>
          <p className="text-red-400/70 text-xs mt-1">
            {error instanceof Error ? error.message : 'Make sure the backend is running.'}
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-6">
        {/* Streak Card */}
        <div className="md:col-span-1">
          {isLoading ? (
            <SkeletonBlock className="h-40" />
          ) : data ? (
            <StreakCard
              currentStreak={data.current_streak}
              longestStreak={data.longest_streak}
              totalAttempts={data.total_attempts}
            />
          ) : null}
        </div>

        {/* Band Display */}
        <div className="md:col-span-1">
          {isLoading ? (
            <SkeletonBlock className="h-40" />
          ) : !isError ? (
            <BandDisplay band={data?.estimated_band ?? null} />
          ) : null}
        </div>

        {/* Quick Stats */}
        <div className="md:col-span-1">
          <div className="bg-card border border-cardBorder rounded-xl p-5 h-full">
            <p className="text-textSecondary text-xs font-semibold uppercase tracking-wider mb-3">
              Stats
            </p>
            {isLoading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-4 bg-background animate-pulse rounded" />
                ))}
              </div>
            ) : data ? (
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-textSecondary text-sm">Total attempts</span>
                  <span className="text-textPrimary font-semibold">{data.total_attempts}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-textSecondary text-sm">Longest streak</span>
                  <span className="text-textPrimary font-semibold">{data.longest_streak} days</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-textSecondary text-sm">Current streak</span>
                  <span className="text-accent font-semibold">{data.current_streak} days</span>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      {/* Activity Heatmap */}
      <div className="bg-card border border-cardBorder rounded-xl p-5 mb-6">
        <div className="flex items-center justify-between mb-4">
          <p className="text-textPrimary font-semibold text-sm">Practice Activity</p>
          <p className="text-textSecondary text-xs">Last 6 months</p>
        </div>
        {isLoading ? (
          <SkeletonBlock className="h-24" />
        ) : (
          <ActivityHeatmap values={data?.heatmap ?? []} />
        )}
      </div>

      {/* Quick Launch */}
      <div>
        <p className="text-textPrimary font-semibold text-sm mb-3">Start Practicing</p>
        <div className="grid grid-cols-3 gap-4">
          <PartLaunchButton
            part="P1"
            label="Part 1"
            description="Short Q&A"
            to="/practice/part1"
            color="bg-cyan-600"
          />
          <PartLaunchButton
            part="P2"
            label="Part 2"
            description="Cue card — speak 2 min"
            to="/practice/part2"
            color="bg-purple-600"
          />
          <PartLaunchButton
            part="P3"
            label="Part 3"
            description="Discussion questions"
            to="/practice/part3"
            color="bg-indigo-600"
          />
        </div>
      </div>
    </div>
  )
}
