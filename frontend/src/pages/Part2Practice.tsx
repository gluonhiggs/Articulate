import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchPart2Questions } from '../api/client'
import { ScoreBadge } from '../components/questions/ScoreBadge'
import type { Question } from '../types'
import { PartTabSwitcher } from './PartTabSwitcher'

type Category = 'person' | 'object' | 'activity' | 'place'

const CATEGORIES: { id: Category; label: string; emoji: string }[] = [
  { id: 'person', label: 'Person', emoji: '👤' },
  { id: 'object', label: 'Object', emoji: '📦' },
  { id: 'activity', label: 'Activity', emoji: '🏃' },
  { id: 'place', label: 'Place', emoji: '📍' },
]

function CueCardItem({
  question,
  onClick,
}: {
  question: Question
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left bg-card border border-cardBorder rounded-xl p-5 hover:border-accent/50 hover:shadow-lg hover:shadow-accent/5 hover:-translate-y-0.5 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-accent/50"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <p className="text-textPrimary font-medium text-sm leading-snug flex-1">
          {question.text}
        </p>
        <ScoreBadge score={question.latest_score} size="sm" />
      </div>

      {question.bullet_points && question.bullet_points.length > 0 && (
        <ul className="space-y-1.5 mt-2">
          {question.bullet_points.map((bp, i) => (
            <li key={i} className="text-xs text-textSecondary flex items-start gap-2">
              <span className="text-accent mt-0.5 flex-shrink-0">•</span>
              <span>{bp}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3 flex items-center gap-2">
        <span className="text-xs bg-background text-textSecondary px-2 py-0.5 rounded-full capitalize">
          {question.category ?? 'general'}
        </span>
        <span className="text-xs text-textSecondary">Part 2</span>
      </div>
    </button>
  )
}

export function Part2Practice() {
  const navigate = useNavigate()
  const [activeCategory, setActiveCategory] = useState<Category>('person')
  const [hideAnswered, setHideAnswered] = useState(false)

  const { data: questions, isLoading, isError } = useQuery<Question[]>({
    queryKey: ['questions', 'part2', activeCategory, hideAnswered],
    queryFn: () => fetchPart2Questions(activeCategory, hideAnswered),
    staleTime: 60 * 1000,
  })

  return (
    <div className="flex flex-col min-h-screen">
      {/* Header */}
      <div className="bg-sidebar border-b border-cardBorder px-6 py-4 sticky top-0 z-10">
        <PartTabSwitcher activePart="part2" />
      </div>

      <div className="flex flex-1">
        {/* Left panel — category tabs */}
        <div className="w-72 border-r border-cardBorder bg-sidebar flex-shrink-0 sticky top-[65px] h-[calc(100vh-65px)] overflow-y-auto">
          <div className="p-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-textSecondary text-xs font-semibold uppercase tracking-wider">
                Category
              </p>
              <label className="flex items-center gap-1.5 cursor-pointer">
                <div
                  onClick={() => setHideAnswered((v) => !v)}
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
                <span className="text-textSecondary text-xs">Hide done</span>
              </label>
            </div>

            <div className="space-y-1">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => setActiveCategory(cat.id)}
                  className={[
                    'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors duration-150',
                    activeCategory === cat.id
                      ? 'bg-accent/10 text-accent border-l-2 border-accent pl-[10px]'
                      : 'text-textSecondary hover:text-textPrimary hover:bg-card',
                  ].join(' ')}
                >
                  <span>{cat.emoji}</span>
                  <span>{cat.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right panel — question grid */}
        <div className="flex-1 p-6 overflow-y-auto">
          <div className="mb-4">
            <p className="text-textPrimary font-semibold">
              {CATEGORIES.find((c) => c.id === activeCategory)?.label}
            </p>
            {!isLoading && (
              <p className="text-textSecondary text-xs mt-0.5">
                {questions?.length ?? 0} cue {(questions?.length ?? 0) === 1 ? 'card' : 'cards'}
              </p>
            )}
          </div>

          {isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="h-40 bg-card animate-pulse rounded-xl" />
              ))}
            </div>
          ) : isError ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <p className="text-red-400 text-lg">Could not load questions</p>
              <p className="text-textSecondary text-sm mt-2">Check that the backend is running.</p>
            </div>
          ) : !questions || questions.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <p className="text-textSecondary text-lg">No cue cards</p>
              <p className="text-textSecondary text-sm mt-2">
                No cue cards in this category yet
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {questions.map((q) => (
                <CueCardItem
                  key={q.id}
                  question={q}
                  onClick={() => navigate(`/practice/part2/questions/${q.id}`)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
