import type { ReactNode } from 'react'
import type { QuoteStatus } from './studioModel'

export const inputClass =
  'w-full bg-background border border-cardBorder rounded-lg px-3 py-2 text-sm text-textPrimary placeholder-textSecondary focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent/50 disabled:opacity-50'

export const selectClass =
  'bg-background border border-cardBorder rounded-lg px-2 py-1.5 text-sm text-textPrimary focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent/50 disabled:opacity-50'

export const primaryButtonClass =
  'inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-accent/20 text-accent border border-accent/30 hover:bg-accent/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed'

export const secondaryButtonClass =
  'inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white/5 border border-white/10 text-gray-300 hover:bg-white/10 transition-colors disabled:opacity-40 disabled:cursor-not-allowed'

export const dangerButtonClass =
  'inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed'

export const cardClass = 'bg-card border border-cardBorder rounded-xl p-5'

export function Field({
  label,
  hint,
  className,
  children,
}: {
  label: string
  hint?: ReactNode
  className?: string
  children: ReactNode
}) {
  return (
    <label className={`block ${className ?? ''}`}>
      <span className="block text-xs font-medium text-textSecondary mb-1">{label}</span>
      {children}
      {hint && <span className="block text-[11px] text-gray-500 mt-1">{hint}</span>}
    </label>
  )
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={`inline-block animate-spin h-4 w-4 border-2 border-teal-400 border-t-transparent rounded-full ${className ?? ''}`}
    />
  )
}

const NOTICE_TONES = {
  error: 'bg-red-500/10 border-red-500/20 text-red-400',
  warning: 'bg-amber-500/10 border-amber-500/20 text-amber-300',
  success: 'bg-teal-500/10 border-teal-500/20 text-teal-300',
  info: 'bg-white/5 border-white/10 text-textSecondary',
}

export function Notice({ tone, children }: { tone: keyof typeof NOTICE_TONES; children: ReactNode }) {
  return <div className={`rounded-lg border p-3 text-sm ${NOTICE_TONES[tone]}`}>{children}</div>
}

export function IssueList({ tone, issues }: { tone: 'error' | 'warning'; issues: string[] }) {
  if (issues.length === 0) return null
  return (
    <Notice tone={tone}>
      <ul className="space-y-1 text-xs">
        {issues.map((issue) => (
          <li key={issue}>{issue}</li>
        ))}
      </ul>
    </Notice>
  )
}

const BADGE_TONES = {
  accent: 'bg-teal-500/10 text-teal-400 border-teal-500/30',
  amber: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
  red: 'bg-red-500/10 text-red-400 border-red-500/30',
  gray: 'bg-white/5 text-gray-400 border-white/10',
}

export function Badge({ tone, children }: { tone: keyof typeof BADGE_TONES; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center text-[11px] px-2 py-0.5 rounded-full border whitespace-nowrap ${BADGE_TONES[tone]}`}>
      {children}
    </span>
  )
}

const QUOTE_BADGES: Record<Exclude<QuoteStatus, 'none'>, { tone: keyof typeof BADGE_TONES; label: string }> = {
  verified: { tone: 'accent', label: 'Quote found in sources' },
  unverified: { tone: 'amber', label: 'Quote not found in sources' },
  pending: { tone: 'gray', label: 'Quote checked on save' },
}

export function QuoteBadge({ status }: { status: QuoteStatus }) {
  if (status === 'none') return null
  const badge = QUOTE_BADGES[status]
  return <Badge tone={badge.tone}>{badge.label}</Badge>
}

export function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  label: string
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className="inline-flex items-center gap-2 select-none disabled:opacity-50"
    >
      <span
        className={[
          'w-8 h-4 rounded-full transition-colors duration-200 relative shrink-0',
          checked ? 'bg-accent' : 'bg-cardBorder',
        ].join(' ')}
      >
        <span
          className={[
            'absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white transition-transform duration-200',
            checked ? 'translate-x-4' : 'translate-x-0',
          ].join(' ')}
        />
      </span>
      <span className="text-xs text-textSecondary">{label}</span>
    </button>
  )
}

export function PlusIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  )
}

export function RemoveButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className="p-1 rounded-md text-textSecondary hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-40"
    >
      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
      </svg>
    </button>
  )
}

export function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className={`h-4 w-4 text-textSecondary transition-transform duration-150 ${open ? 'rotate-180' : ''}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  )
}
