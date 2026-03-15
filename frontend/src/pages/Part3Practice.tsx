import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchPart3Questions } from '../api/client'
import { ScoreBadge } from '../components/questions/ScoreBadge'
import type { Part3Group } from '../types'
import { PartTabSwitcher } from './PartTabSwitcher'

type Category = 'person' | 'object' | 'activity' | 'place'

const CATEGORIES: { id: Category; label: string; emoji: string }[] = [
  { id: 'person', label: 'Con người', emoji: '👤' },
  { id: 'object', label: 'Đồ vật', emoji: '📦' },
  { id: 'activity', label: 'Hoạt động', emoji: '🏃' },
  { id: 'place', label: 'Địa điểm', emoji: '📍' },
]

export function Part3Practice() {
  const navigate = useNavigate()
  const [activeCategory, setActiveCategory] = useState<Category>('person')
  const [hideAnswered, setHideAnswered] = useState(false)
  const [selectedGroupIndex, setSelectedGroupIndex] = useState<number>(0)

  const { data: groups, isLoading } = useQuery<Part3Group[]>({
    queryKey: ['questions', 'part3', activeCategory, hideAnswered],
    queryFn: () => fetchPart3Questions(activeCategory, hideAnswered),
    staleTime: 60 * 1000,
  })

  const selectedGroup = groups?.[selectedGroupIndex] ?? null

  return (
    <div className="flex flex-col min-h-screen">
      {/* Header */}
      <div className="bg-sidebar border-b border-cardBorder px-6 py-4 sticky top-0 z-10">
        <PartTabSwitcher activePart="part3" />
      </div>

      <div className="flex flex-1">
        {/* Left panel — category + topic list */}
        <div className="w-72 border-r border-cardBorder bg-sidebar flex-shrink-0 sticky top-[65px] h-[calc(100vh-65px)] overflow-y-auto">
          <div className="p-4">
            {/* Category filter */}
            <div className="flex items-center justify-between mb-3">
              <p className="text-textSecondary text-xs font-semibold uppercase tracking-wider">
                Danh mục
              </p>
              <label className="flex items-center gap-1.5 cursor-pointer">
                <div
                  onClick={() => {
                    setHideAnswered((v) => !v)
                    setSelectedGroupIndex(0)
                  }}
                  className={[
                    'w-8 h-4 rounded-full transition-colors duration-200 relative',
                    hideAnswered ? 'bg-accent' : 'bg-cardBorder',
                  ].join(' ')}
                >
                  <span
                    className={[
                      'absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white transition-transform duration-200',
                      hideAnswered ? 'translate-x-4' : 'translate-x-0',
                    ].join(' ')}
                  />
                </div>
                <span className="text-textSecondary text-xs">Ẩn đã làm</span>
              </label>
            </div>

            <div className="flex flex-wrap gap-1 mb-4">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => {
                    setActiveCategory(cat.id)
                    setSelectedGroupIndex(0)
                  }}
                  className={[
                    'px-2.5 py-1 rounded-full text-xs transition-colors duration-150',
                    activeCategory === cat.id
                      ? 'bg-accent/20 text-accent border border-accent/30'
                      : 'bg-card text-textSecondary border border-cardBorder hover:text-textPrimary',
                  ].join(' ')}
                >
                  {cat.emoji} {cat.label}
                </button>
              ))}
            </div>

            {/* Topic list */}
            <p className="text-textSecondary text-xs font-semibold uppercase tracking-wider mb-2">
              Chủ đề
            </p>
            {isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="h-10 bg-card animate-pulse rounded-lg" />
                ))}
              </div>
            ) : !groups || groups.length === 0 ? (
              <p className="text-textSecondary text-sm py-4 text-center">Không có chủ đề</p>
            ) : (
              <div className="space-y-1">
                {groups.map((group, i) => (
                  <button
                    key={group.parent.id}
                    onClick={() => setSelectedGroupIndex(i)}
                    className={[
                      'w-full text-left px-3 py-2 rounded-lg text-sm transition-colors duration-150',
                      selectedGroupIndex === i
                        ? 'bg-accent/10 text-accent border-l-2 border-accent pl-[10px]'
                        : 'text-textSecondary hover:text-textPrimary hover:bg-card',
                    ].join(' ')}
                  >
                    <p className="line-clamp-2 leading-snug">{group.parent.text}</p>
                    <p className="text-xs mt-0.5 opacity-60">{group.questions.length} câu</p>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right panel — Part 3 group cards */}
        <div className="flex-1 p-6 overflow-y-auto">
          {isLoading ? (
            <div className="space-y-4">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-48 bg-card animate-pulse rounded-xl" />
              ))}
            </div>
          ) : !selectedGroup ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <p className="text-textSecondary text-lg">Chọn một chủ đề</p>
              <p className="text-textSecondary text-sm mt-2">
                Chọn chủ đề từ danh sách bên trái
              </p>
            </div>
          ) : (
            <div>
              {/* Parent question context */}
              <div className="bg-card border border-cardBorder rounded-xl p-5 mb-5">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs bg-purple-500/20 text-purple-300 border border-purple-500/30 px-2 py-0.5 rounded-full">
                    Part 2 — Cue Card
                  </span>
                </div>
                <p className="text-textPrimary font-medium">{selectedGroup.parent.text}</p>
                {selectedGroup.parent.bullet_points && (
                  <ul className="mt-3 space-y-1">
                    {selectedGroup.parent.bullet_points.map((bp, i) => (
                      <li key={i} className="text-xs text-textSecondary flex items-start gap-2">
                        <span className="text-accent mt-0.5">•</span>
                        <span>{bp}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Part 3 questions */}
              <p className="text-textSecondary text-xs font-semibold uppercase tracking-wider mb-3">
                Câu hỏi Part 3 liên quan
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {selectedGroup.questions.map((q) => (
                  <button
                    key={q.id}
                    onClick={() => navigate(`/practice/${q.id}`)}
                    className="text-left bg-card border border-cardBorder rounded-xl p-4 hover:border-accent/50 hover:shadow-lg hover:shadow-accent/5 hover:-translate-y-0.5 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-accent/50"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-textPrimary text-sm font-medium leading-snug flex-1">
                        {q.text}
                      </p>
                      <ScoreBadge score={q.latest_score} size="sm" />
                    </div>
                    <p className="text-xs text-textSecondary mt-2">Part 3 — Discussion</p>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
