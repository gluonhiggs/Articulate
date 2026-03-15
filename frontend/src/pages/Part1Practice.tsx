import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchPart1Questions } from '../api/client'
import { QuestionCard } from '../components/questions/QuestionCard'
import type { Question } from '../types'
import { PartTabSwitcher } from './PartTabSwitcher'

export function Part1Practice() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [hideAnswered, setHideAnswered] = useState(false)

  const { data: questions, isLoading } = useQuery<Question[]>({
    queryKey: ['questions', 'part1', hideAnswered],
    queryFn: () => fetchPart1Questions(hideAnswered),
    staleTime: 60 * 1000,
  })

  const filtered = useMemo(() => {
    if (!questions) return []
    const q = search.trim().toLowerCase()
    if (!q) return questions
    return questions.filter((item) => item.text.toLowerCase().includes(q))
  }, [questions, search])

  function handleClick(question: Question) {
    navigate(`/practice/${question.id}`)
  }

  return (
    <div className="flex flex-col min-h-screen">
      {/* Header */}
      <div className="bg-sidebar border-b border-cardBorder px-6 py-4 sticky top-0 z-10">
        <PartTabSwitcher activePart="part1" />
      </div>

      <div className="p-6 flex-1">
        {/* Controls */}
        <div className="flex items-center gap-4 mb-6">
          <div className="flex-1 relative">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-textSecondary"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
            >
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="text"
              placeholder="Tìm kiếm câu hỏi..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-card border border-cardBorder rounded-lg pl-9 pr-4 py-2 text-sm text-textPrimary placeholder-textSecondary focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent/50"
            />
          </div>

          <label className="flex items-center gap-2 cursor-pointer select-none">
            <div
              onClick={() => setHideAnswered((v) => !v)}
              className={[
                'w-10 h-5 rounded-full transition-colors duration-200 relative',
                hideAnswered ? 'bg-accent' : 'bg-cardBorder',
              ].join(' ')}
            >
              <span
                className={[
                  'absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform duration-200',
                  hideAnswered ? 'translate-x-5' : 'translate-x-0',
                ].join(' ')}
              />
            </div>
            <span className="text-textSecondary text-sm">Ẩn đã trả lời</span>
          </label>
        </div>

        {/* Results count */}
        {!isLoading && (
          <p className="text-textSecondary text-xs mb-4">
            {filtered.length} câu hỏi
            {search && ` phù hợp với "${search}"`}
          </p>
        )}

        {/* Question grid */}
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 9 }).map((_, i) => (
              <div key={i} className="h-32 bg-card animate-pulse rounded-xl" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <p className="text-textSecondary text-lg">Không tìm thấy câu hỏi</p>
            <p className="text-textSecondary text-sm mt-2">
              {search ? 'Thử từ khóa khác' : 'Tất cả câu hỏi đã được trả lời'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((q) => (
              <QuestionCard key={q.id} question={q} onClick={handleClick} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
