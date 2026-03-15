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
        <p className="text-textSecondary text-sm">Chưa có dữ liệu</p>
        <p className="text-xs text-textSecondary mt-1">Luyện thêm để xem band score</p>
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
  const { data, isLoading, isError } = useQuery<DashboardData>({
    queryKey: ['dashboard'],
    queryFn: fetchDashboard,
    staleTime: 60 * 1000,
  })

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-textPrimary">Trang chủ</h1>
        <p className="text-textSecondary text-sm mt-1">Tiến độ luyện tập IELTS Speaking của bạn</p>
      </div>

      {isError && (
        <div className="bg-red-900/20 border border-red-500/30 rounded-xl p-4 mb-6">
          <p className="text-red-400 text-sm">Không thể tải dữ liệu. Hãy kiểm tra kết nối server.</p>
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
          ) : (
            <BandDisplay band={data?.estimated_band ?? null} />
          )}
        </div>

        {/* Quick Stats */}
        <div className="md:col-span-1">
          <div className="bg-card border border-cardBorder rounded-xl p-5 h-full">
            <p className="text-textSecondary text-xs font-semibold uppercase tracking-wider mb-3">
              Thống kê
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
                  <span className="text-textSecondary text-sm">Tổng lần luyện</span>
                  <span className="text-textPrimary font-semibold">{data.total_attempts}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-textSecondary text-sm">Streak dài nhất</span>
                  <span className="text-textPrimary font-semibold">{data.longest_streak} ngày</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-textSecondary text-sm">Streak hiện tại</span>
                  <span className="text-accent font-semibold">{data.current_streak} ngày 🔥</span>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      {/* Activity Heatmap */}
      <div className="bg-card border border-cardBorder rounded-xl p-5 mb-6">
        <div className="flex items-center justify-between mb-4">
          <p className="text-textPrimary font-semibold text-sm">Hoạt động luyện tập</p>
          <p className="text-textSecondary text-xs">5 tháng gần nhất</p>
        </div>
        {isLoading ? (
          <SkeletonBlock className="h-24" />
        ) : (
          <ActivityHeatmap values={data?.heatmap ?? []} />
        )}
      </div>

      {/* Quick Launch */}
      <div>
        <p className="text-textPrimary font-semibold text-sm mb-3">Bắt đầu luyện tập</p>
        <div className="grid grid-cols-3 gap-4">
          <PartLaunchButton
            part="P1"
            label="Part 1"
            description="Câu hỏi hỏi đáp ngắn"
            to="/practice/part1"
            color="bg-cyan-600"
          />
          <PartLaunchButton
            part="P2"
            label="Part 2"
            description="Cue card — nói 2 phút"
            to="/practice/part2"
            color="bg-purple-600"
          />
          <PartLaunchButton
            part="P3"
            label="Part 3"
            description="Câu hỏi thảo luận"
            to="/practice/part3"
            color="bg-indigo-600"
          />
        </div>
      </div>
    </div>
  )
}
