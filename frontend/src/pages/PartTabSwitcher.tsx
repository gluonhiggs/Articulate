import { Link } from 'react-router-dom'

interface PartTabSwitcherProps {
  activePart: 'part1' | 'part2' | 'part3'
}

const tabs = [
  { id: 'part1' as const, label: 'Part 1', to: '/practice/part1' },
  { id: 'part2' as const, label: 'Part 2', to: '/practice/part2' },
  { id: 'part3' as const, label: 'Part 3', to: '/practice/part3' },
]

export function PartTabSwitcher({ activePart }: PartTabSwitcherProps) {
  return (
    <div className="flex items-center gap-1 bg-background rounded-lg p-1 w-fit">
      {tabs.map((tab) => (
        <Link
          key={tab.id}
          to={tab.to}
          className={[
            'px-4 py-1.5 rounded-md text-sm font-medium transition-colors duration-150',
            activePart === tab.id
              ? 'bg-card text-textPrimary shadow'
              : 'text-textSecondary hover:text-textPrimary',
          ].join(' ')}
        >
          {tab.label}
        </Link>
      ))}
    </div>
  )
}
