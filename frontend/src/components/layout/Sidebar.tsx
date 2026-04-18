import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { fetchSystemInfo, patchLlmModel, patchTranscriptionMode } from '../../api/client'
import type { SystemInfo } from '../../types'

interface NavItem {
  label: string
  to: string
  icon: React.ReactNode
}

function HomeIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className="h-5 w-5"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
      />
    </svg>
  )
}

function MicrophoneIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className="h-5 w-5"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
      />
    </svg>
  )
}

function ClipboardIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className="h-5 w-5"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
      />
    </svg>
  )
}

function ChartIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className="h-5 w-5"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
    >
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  )
}

function CpuIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className="h-4 w-4"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
    >
      <rect x="4" y="4" width="16" height="16" rx="2" ry="2" />
      <rect x="9" y="9" width="6" height="6" />
      <line x1="9" y1="1" x2="9" y2="4" />
      <line x1="15" y1="1" x2="15" y2="4" />
      <line x1="9" y1="20" x2="9" y2="23" />
      <line x1="15" y1="20" x2="15" y2="23" />
      <line x1="20" y1="9" x2="23" y2="9" />
      <line x1="20" y1="14" x2="23" y2="14" />
      <line x1="1" y1="9" x2="4" y2="9" />
      <line x1="1" y1="14" x2="4" y2="14" />
    </svg>
  )
}

const navItems: NavItem[] = [
  { label: 'Home', to: '/', icon: <HomeIcon /> },
  { label: 'Practice', to: '/practice/part1', icon: <MicrophoneIcon /> },
  { label: 'Mock Test', to: '/mock-test', icon: <ClipboardIcon /> },
  { label: 'Forecast', to: '/forecast', icon: <ChartIcon /> },
]

function PencilIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className="h-3 w-3"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
      />
    </svg>
  )
}

function SpinnerIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className="h-3 w-3 animate-spin"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
    </svg>
  )
}

export function Sidebar({ onClose }: { onClose?: () => void }) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const { data: systemInfo, isError: systemInfoError } = useQuery<SystemInfo>({
    queryKey: ['systemInfo'],
    queryFn: fetchSystemInfo,
    staleTime: 5 * 60 * 1000,
    retry: false,
    refetchInterval: (query) => {
      const d = query.state.data
      return d?.op_status ? 2000 : false
    },
  })

  const modelMutation = useMutation({
    mutationFn: patchLlmModel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['systemInfo'] })
      setEditing(false)
    },
  })

  const modeMutation = useMutation({
    mutationFn: patchTranscriptionMode,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['systemInfo'] })
    },
  })

  function startEditing() {
    setDraft(systemInfo?.llm_model ?? '')
    setEditing(true)
    setTimeout(() => inputRef.current?.select(), 0)
  }

  function commitEdit() {
    const trimmed = draft.trim()
    if (trimmed && trimmed !== systemInfo?.llm_model) {
      modelMutation.mutate(trimmed)
    } else {
      setEditing(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') commitEdit()
    if (e.key === 'Escape') setEditing(false)
  }

  return (
    <aside className="w-64 min-h-screen bg-sidebar flex flex-col border-r border-cardBorder">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-cardBorder">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-purple-600 flex items-center justify-center">
            <span className="text-white font-bold text-sm">A</span>
          </div>
          <div>
            <p className="text-textPrimary font-semibold text-sm leading-tight">Articulate</p>
            <p className="text-textSecondary text-xs">Local Kit</p>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="md:hidden ml-auto p-1 text-textSecondary hover:text-textPrimary"
              aria-label="Close menu"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            onClick={onClose}
            className={({ isActive }) =>
              [
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors duration-150',
                isActive
                  ? 'bg-accent/10 text-accent border-l-2 border-accent pl-[10px]'
                  : 'text-textSecondary hover:text-textPrimary hover:bg-card',
              ].join(' ')
            }
          >
            {item.icon}
            <span>{item.label}</span>
          </NavLink>
        ))}

        {/* Practice sub-links */}
        <div className="pt-2 pb-1 px-3">
          <p className="text-xs font-semibold text-textSecondary uppercase tracking-wider">
            Speaking Parts
          </p>
        </div>
        {[
          { label: 'Part 1 - Q&A', to: '/practice/part1' },
          { label: 'Part 2 - Cue Card', to: '/practice/part2' },
          { label: 'Part 3 - Discussion', to: '/practice/part3' },
        ].map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onClose}
            className={({ isActive }) =>
              [
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors duration-150 ml-2',
                isActive
                  ? 'bg-accent/10 text-accent border-l-2 border-accent pl-[10px]'
                  : 'text-textSecondary hover:text-textPrimary hover:bg-card',
              ].join(' ')
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* System Info */}
      <div className="px-4 py-4 border-t border-cardBorder">
        <div className="flex items-start gap-2">
          <div className="text-textSecondary mt-0.5">
            <CpuIcon />
          </div>
          <div className="flex-1 min-w-0">
            {systemInfo ? (
              <>
                <p className="text-xs text-textSecondary truncate">
                  <span className="text-textPrimary font-medium">{systemInfo.profile}</span>
                </p>
                <p className="text-xs text-textSecondary truncate mt-0.5">
                  Whisper: {systemInfo.whisper_model}
                </p>
                {editing ? (
                  <input
                    ref={inputRef}
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onBlur={commitEdit}
                    onKeyDown={handleKeyDown}
                    className="text-xs w-full bg-card border border-accent/40 rounded px-1 py-0.5 text-textPrimary outline-none focus:border-accent"
                    autoFocus
                  />
                ) : (
                  <button
                    onClick={startEditing}
                    className="group flex items-center gap-1 text-xs text-textSecondary hover:text-textPrimary w-full text-left"
                    title="Click to change model"
                  >
                    <span className="truncate">LLM: {systemInfo.llm_model}</span>
                    <span className="shrink-0 opacity-0 group-hover:opacity-60 transition-opacity">
                      {modelMutation.isPending ? <SpinnerIcon /> : <PencilIcon />}
                    </span>
                  </button>
                )}
                {systemInfo.is_low_accuracy && (
                  <span className="mt-1.5 inline-block text-xs text-amber-400 border border-amber-400/30 rounded px-1.5 py-0.5">
                    Low-accuracy mode
                  </span>
                )}
                {!systemInfo.llm_reachable && (
                  <span className="mt-1.5 inline-block text-xs text-red-400 border border-red-400/30 rounded px-1.5 py-0.5">
                    ⚠ LLM unreachable
                  </span>
                )}

                {/* ── Transcription mode switcher ──
                    Visible when the runtime has faster-whisper bundled OR the auto-install
                    path is available (source installs). Both CPU and GPU installer variants
                    ship faster-whisper, so packaged users always see this. */}
                {(systemInfo.faster_whisper_installed || !systemInfo.is_desktop) && <div className="mt-3 rounded-lg border border-cardBorder bg-card p-2.5">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-textSecondary mb-2">
                    Transcription
                  </p>
                  <div className="flex gap-1.5">
                    <button
                      onClick={() => modeMutation.mutate('groq')}
                      disabled={
                        systemInfo.transcription_mode === 'groq' ||
                        (!!systemInfo.op_status && systemInfo.op_status !== 'failed')
                      }
                      className={[
                        'flex-1 rounded-md border px-2 py-1 text-[11px] font-medium transition-colors',
                        systemInfo.transcription_mode === 'groq'
                          ? 'border-accent/40 bg-accent/10 text-accent'
                          : 'border-cardBorder text-textSecondary hover:text-textPrimary hover:border-slate-500 disabled:opacity-40 disabled:cursor-not-allowed',
                      ].join(' ')}
                    >
                      ☁ Cloud
                    </button>
                    <button
                      onClick={() => modeMutation.mutate('local')}
                      disabled={
                        systemInfo.transcription_mode === 'local' ||
                        (!!systemInfo.op_status && systemInfo.op_status !== 'failed')
                      }
                      className={[
                        'flex-1 rounded-md border px-2 py-1 text-[11px] font-medium transition-colors',
                        systemInfo.transcription_mode === 'local'
                          ? 'border-accent/40 bg-accent/10 text-accent'
                          : 'border-cardBorder text-textSecondary hover:text-textPrimary hover:border-slate-500 disabled:opacity-40 disabled:cursor-not-allowed',
                      ].join(' ')}
                    >
                      ⚡ Local
                    </button>
                  </div>

                  {/* faster-whisper not installed */}
                  {!systemInfo.faster_whisper_installed &&
                    !systemInfo.op_status &&
                    systemInfo.transcription_mode === 'groq' && (
                      <p className="mt-2 text-[10px] text-amber-400/80">
                        Click ⚡ Local to auto-install faster-whisper.
                      </p>
                    )}

                  {/* Installing */}
                  {systemInfo.op_status === 'installing' && (
                    <div className="mt-2">
                      <div className="flex items-center gap-1.5 text-[11px] text-sky-400">
                        <SpinnerIcon />
                        Installing faster-whisper…
                      </div>
                      <div className="mt-1.5 h-0.5 w-full overflow-hidden rounded bg-cardBorder">
                        <div className="h-full bg-sky-500 rounded [animation:progress_2s_ease-in-out_infinite_alternate]" />
                      </div>
                    </div>
                  )}

                  {/* Loading model */}
                  {systemInfo.op_status === 'loading' && (
                    <div className="mt-2">
                      <div className="flex items-center gap-1.5 text-[11px] text-sky-400">
                        <SpinnerIcon />
                        Loading model…
                      </div>
                      <div className="mt-1.5 h-0.5 w-full overflow-hidden rounded bg-cardBorder">
                        <div className="h-full bg-sky-500 rounded [animation:progress_2s_ease-in-out_infinite_alternate]" />
                      </div>
                    </div>
                  )}

                  {/* Local active */}
                  {systemInfo.transcription_mode === 'local' && !systemInfo.op_status && (
                    <span className={[
                      'mt-2 inline-block text-[10px] rounded px-1.5 py-0.5 border font-medium',
                      systemInfo.whisper_device === 'cuda'
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                        : 'bg-amber-500/10 text-amber-400 border-amber-500/30',
                    ].join(' ')}>
                      {systemInfo.whisper_device === 'cuda'
                        ? `GPU · ${systemInfo.whisper_model}`
                        : `CPU · ~40-60s/answer`}
                    </span>
                  )}

                  {/* Cloud active - pronunciation accuracy note */}
                  {systemInfo.transcription_mode === 'groq' &&
                    !systemInfo.op_status && (
                      <span className="mt-2 inline-block text-[10px] rounded px-1.5 py-0.5 border font-medium bg-amber-500/10 text-amber-400 border-amber-500/30">
                        Pronunciation accuracy limited
                      </span>
                    )}

                  {/* Operation failed */}
                  {systemInfo.op_status === 'failed' && (
                    <p className="mt-2 text-[10px] text-red-400">
                      ⚠ Operation failed - check server logs.
                    </p>
                  )}
                </div>}
              </>
            ) : systemInfoError ? (
              <p className="text-xs text-red-400">Backend offline</p>
            ) : (
              <p className="text-xs text-textSecondary">Loading...</p>
            )}
          </div>
        </div>
      </div>
    </aside>
  )
}
