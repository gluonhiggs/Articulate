import { useState } from 'react'

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className={`h-3.5 w-3.5 shrink-0 text-textSecondary transition-transform ${open ? 'rotate-90' : ''}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.5}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
    </svg>
  )
}

export function Disclosure({
  title,
  summary,
  defaultOpen = false,
  children,
}: {
  title: string
  summary?: string
  defaultOpen?: boolean
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="bg-card/40 border border-white/5 rounded-xl">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="w-full flex items-center gap-2.5 px-4 py-3 text-left rounded-xl hover:bg-white/[0.03] transition-colors"
      >
        <Chevron open={open} />
        <span className="text-sm font-medium text-textPrimary">{title}</span>
        {summary && <span className="ml-auto text-xs text-textSecondary truncate pl-3">{summary}</span>}
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  )
}
