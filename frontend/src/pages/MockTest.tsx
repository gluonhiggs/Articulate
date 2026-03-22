import { useState } from 'react'

type TestFilter = 'all' | 'part1' | 'part2' | 'part3' | 'full'

const FILTERS: { id: TestFilter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'part1', label: 'Part 1' },
  { id: 'part2', label: 'Part 2' },
  { id: 'part3', label: 'Part 3' },
  { id: 'full', label: 'Full Test' },
]

export function MockTest() {
  const [activeFilter, setActiveFilter] = useState<TestFilter>('all')

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-textPrimary">Mock Test</h1>
        <p className="text-textSecondary text-sm mt-1">
          Simulate a real IELTS Speaking exam
        </p>
      </div>

      {/* Filter tabs */}
      <div className="flex items-center gap-2 mb-8 flex-wrap">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            onClick={() => setActiveFilter(f.id)}
            className={[
              'px-4 py-2 rounded-lg text-sm font-medium transition-colors duration-150',
              activeFilter === f.id
                ? 'bg-accent/20 text-accent border border-accent/30'
                : 'bg-card text-textSecondary border border-cardBorder hover:text-textPrimary hover:border-cardBorder/80',
            ].join(' ')}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Coming soon state */}
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <div className="w-20 h-20 rounded-full bg-card border border-cardBorder flex items-center justify-center mb-6">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-10 w-10 text-textSecondary"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>

        <h2 className="text-textPrimary text-xl font-semibold mb-2">Coming Soon</h2>
        <p className="text-textSecondary text-sm max-w-sm leading-relaxed">
          The mock test feature is under development. You'll be able to practice a full IELTS
          Speaking exam in real time.
        </p>

        <div className="mt-8 grid grid-cols-1 sm:grid-cols-3 gap-4 w-full max-w-lg">
          {[
            {
              title: 'Part 1',
              desc: '4–5 min, short questions about yourself',
              icon: '💬',
            },
            {
              title: 'Part 2',
              desc: '3–4 min, speak about a cue card',
              icon: '📋',
            },
            {
              title: 'Part 3',
              desc: '4–5 min, topic discussion',
              icon: '🗣️',
            },
          ].map((part) => (
            <div
              key={part.title}
              className="bg-card border border-cardBorder rounded-xl p-4 text-center opacity-60"
            >
              <div className="text-2xl mb-2">{part.icon}</div>
              <p className="text-textPrimary font-semibold text-sm">{part.title}</p>
              <p className="text-textSecondary text-xs mt-1">{part.desc}</p>
            </div>
          ))}
        </div>

        <div className="mt-8 bg-card border border-accent/20 rounded-xl p-4 max-w-sm w-full">
          <p className="text-accent text-sm font-medium">When will it launch?</p>
          <p className="text-textSecondary text-xs mt-1">
            The Full Mock Test feature will be available in the next version. In the meantime,
            practice individual questions in Part 1, 2, and 3.
          </p>
        </div>
      </div>
    </div>
  )
}
