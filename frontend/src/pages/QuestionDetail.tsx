import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  fetchAttemptHistory,
  fetchPart1Questions,
  fetchPart2Questions,
  fetchPart3Questions,
  fetchQuestion,
  submitAttempt,
} from '../api/client'
import { RightPanel } from '../components/ai-panel/RightPanel'
import { ActiveAttemptCard } from '../components/questions/ActiveAttemptCard'
import { PrevAttemptCard } from '../components/questions/PrevAttemptCard'
import { partLabel, partMaxSeconds, partRoute } from '../components/questions/utils'
import { RecordingBar } from '../components/recording/RecordingBar'
import { useRecorder } from '../hooks/useRecorder'
import { usePolling } from '../hooks/usePolling'
import { useRecordingStore } from '../store/recordingStore'
import type { Attempt, Part3Group, Question } from '../types'

// ── Constants ────────────────────────────────────────────────────────────────

const PROCESSING_STATUSES = ['processing', 'transcribing', 'scoring']
const COMPANION_MAX_AGE_MS = 5 * 60 * 1000 // ignore attempts older than 5 min
const ERROR_MESSAGES: Record<string, string> = {
  'failed:transcription': 'Could not transcribe audio',
  'failed:empty_audio':   'Audio was too quiet or silent',
  'failed:scoring':       'AI scoring unavailable - check your LLM API key',
}

// ── Main page ───────────────────────────────────────────────────────────────

export function QuestionDetail() {
  const { questionId: questionIdStr } = useParams<{ questionId: string }>()
  const questionId = Number(questionIdStr)
  const queryClient = useQueryClient()

  // Recording store
  const {
    status,
    elapsedSeconds,
    maxSeconds,
    attemptId,
    errorMessage,
    startPreparing,
    startRecording,
    setUploading,
    setPolling,
    setDone,
    setError,
    reset,
    tickElapsed,
  } = useRecordingStore()

  // Upload guard ref - declared early so question-change effect can reset it
  const hasUploadedRef = useRef(false)
  // Pending-stop ref: set when Stop is clicked before MediaRecorder has started
  const pendingStopRef = useRef(false)

  // Fetch question
  const { data: question, isLoading: questionLoading, isError: questionError } = useQuery<Question>({
    queryKey: ['question', questionId],
    queryFn: () => fetchQuestion(questionId),
    enabled: !isNaN(questionId),
  })

  // Fetch attempt history
  const { data: attempts, refetch: refetchAttempts } = useQuery<Attempt[]>({
    queryKey: ['attempts', 'history', questionId],
    queryFn: () => fetchAttemptHistory(questionId),
    enabled: !isNaN(questionId),
    staleTime: 0,
  })

  // Fetch the full question list for this part (for navigation arrows)
  const part = question?.part ?? null

  const { data: part1Questions } = useQuery<Question[]>({
    queryKey: ['questions', 'part1', false],
    queryFn: () => fetchPart1Questions(false),
    enabled: part === '1',
    staleTime: 60 * 1000,
  })

  const { data: part2Questions } = useQuery<Question[]>({
    queryKey: ['questions', 'part2', null, false],
    queryFn: () => fetchPart2Questions(null, false),
    enabled: part === '2',
    staleTime: 60 * 1000,
  })

  const { data: part3Groups } = useQuery<Part3Group[]>({
    queryKey: ['questions', 'part3', null, false],
    queryFn: () => fetchPart3Questions(null, false),
    enabled: part === '3',
    staleTime: 60 * 1000,
  })

  // Flatten Part 3 groups into a flat question list for navigation
  const part3Questions = useMemo<Question[]>(() => {
    if (!part3Groups) return []
    return part3Groups.flatMap((g) => g.questions)
  }, [part3Groups])

  const allQuestions: Question[] = useMemo(() => {
    if (part === '1') return part1Questions ?? []
    if (part === '2') return part2Questions ?? []
    if (part === '3') return part3Questions
    return []
  }, [part, part1Questions, part2Questions, part3Questions])

  // TTS playback for the question
  const ttsAudioRef = useRef<HTMLAudioElement | null>(null)
  const [ttsPlaying, setTtsPlaying] = useState(false)

  function playQuestionTTS(): Promise<void> {
    if (!question) return Promise.resolve()
    if (ttsAudioRef.current) { ttsAudioRef.current.pause(); ttsAudioRef.current = null }
    setTtsPlaying(true)
    return fetch(`/api/v1/tts/${question.id}`)
      .then((res) => {
        if (!res.ok) throw new Error(`TTS error: ${res.status}`)
        return res.blob()
      })
      .then((blob) => {
        const audio = new Audio(URL.createObjectURL(blob))
        ttsAudioRef.current = audio
        audio.onended = () => { setTtsPlaying(false); URL.revokeObjectURL(audio.src) }
        audio.onerror = () => { setTtsPlaying(false); URL.revokeObjectURL(audio.src) }
        return audio.play()
      })
      .catch((err: unknown) => {
        setTtsPlaying(false)
        throw err
      })
  }

  // Auto-play TTS when question loads
  useEffect(() => {
    if (!question) return
    const timer = setTimeout(() => {
      playQuestionTTS().catch((err: unknown) => {
        // Silent fail on mobile (NotAllowedError = no user gesture yet)
        if (err instanceof Error && err.name !== 'NotAllowedError') {
          console.error('Question TTS auto-play failed:', err)
        }
      })
    }, 400)
    return () => clearTimeout(timer)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question?.id])

  // Cleanup TTS on unmount or question change
  useEffect(() => {
    return () => {
      if (ttsAudioRef.current) { ttsAudioRef.current.pause(); ttsAudioRef.current.src = ''; ttsAudioRef.current = null }
      setTtsPlaying(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question?.id])

  // Recorder hook
  const maxSec = question ? partMaxSeconds(question.part) : 45
  const { isRecording, startRecording: startMediaRecorder, stopRecording, audioBlob, resetAudioBlob } = useRecorder(maxSec)

  // Reset store when questionId changes
  const prevQuestionIdRef = useRef(questionId)
  useEffect(() => {
    if (prevQuestionIdRef.current !== questionId) {
      reset()
      resetAudioBlob()
      hasUploadedRef.current = false
      pendingStopRef.current = false
      prevQuestionIdRef.current = questionId
      setPronunAttempt(null)
      setShownPronunIds(new Set())
    }
  }, [questionId, reset, resetAudioBlob])

  // Polling
  const { data: polledAttempt, isTimedOut: pollingTimedOut } = usePolling(attemptId)
  const [newestAttemptId, setNewestAttemptId] = useState<number | null>(null)

  // Right panel state
  const [pronunAttempt, setPronunAttempt] = useState<Attempt | null>(null)
  const [shownPronunIds, setShownPronunIds] = useState<Set<number>>(new Set())

  // Mobile: toggle AI panel
  const [showPanel, setShowPanel] = useState(false)

  // Selected (expanded) attempt - defaults to latest ready
  const [selectedAttemptId, setSelectedAttemptId] = useState<number | null>(null)

  // Timer tick
  useEffect(() => {
    if (status !== 'recording' && status !== 'preparing') return
    const interval = setInterval(() => tickElapsed(), 1000)
    return () => clearInterval(interval)
  }, [status, tickElapsed])

  // Deferred stop: fires when MediaRecorder finally starts after a Stop was
  // requested during the getUserMedia initialisation window
  useEffect(() => {
    if (isRecording && pendingStopRef.current) {
      pendingStopRef.current = false
      stopRecording()
    }
  }, [isRecording, stopRecording])

  // Upload effect
  useEffect(() => {
    if (!audioBlob || isRecording || status !== 'recording') return
    if (hasUploadedRef.current) return
    hasUploadedRef.current = true
    setUploading()
    submitAttempt(questionId, audioBlob)
      .then((res) => { setPolling(res.id); setNewestAttemptId(res.id) })
      .catch((err: unknown) => { setError(err instanceof Error ? err.message : 'Upload failed') })
  }, [audioBlob, isRecording, status, questionId, setUploading, setPolling, setError])

  // Polling result
  useEffect(() => {
    if (pollingTimedOut && status === 'polling') {
      setError('Scoring timed out - the server is taking too long. Please try again.')
      return
    }
    if (!polledAttempt) return
    if (polledAttempt.status === 'ready') {
      setDone()
      queryClient.invalidateQueries({ queryKey: ['attempts', 'history', questionId] })
      queryClient.invalidateQueries({ queryKey: ['questions', 'part1'] })
      queryClient.invalidateQueries({ queryKey: ['questions', 'part2'] })
      queryClient.invalidateQueries({ queryKey: ['questions', 'part3'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      void refetchAttempts()
    } else if (!PROCESSING_STATUSES.includes(polledAttempt.status)) {
      setError(ERROR_MESSAGES[polledAttempt.status] ?? 'Scoring failed')
      queryClient.invalidateQueries({ queryKey: ['attempts', 'history', questionId] })
      void refetchAttempts()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [polledAttempt, pollingTimedOut, status, setDone, setError, queryClient, questionId, refetchAttempts])

  // Companion sync - pick up an in-progress attempt recorded on another device
  const { data: companionAttempt } = useQuery({
    queryKey: ['companion-watch', questionId],
    queryFn: () => fetchAttemptHistory(questionId),
    enabled: attemptId === null && !isNaN(questionId),
    refetchInterval: 4000,
    select: (data: Attempt[]) => {
      const cutoff = Date.now() - COMPANION_MAX_AGE_MS
      return (
        data.find(
          (a) =>
            PROCESSING_STATUSES.includes(a.status) &&
            new Date(a.created_at).getTime() > cutoff,
        ) ?? null
      )
    },
    staleTime: 0,
  })

  useEffect(() => {
    if (companionAttempt && attemptId === null) {
      setPolling(companionAttempt.id)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companionAttempt, attemptId])

  // Auto-transition: preparing -> recording
  useEffect(() => {
    if (status !== 'preparing' || !question) return
    if (question.part !== '2') {
      startRecording()
      hasUploadedRef.current = false
      startMediaRecorder().catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Microphone access denied')
      })
    }
  }, [status, question, startRecording, startMediaRecorder, setError])

  // Part 2 countdown
  const part2PrepTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => {
    if (status !== 'preparing' || question?.part !== '2') return
    part2PrepTimerRef.current = setTimeout(() => {
      startRecording()
      hasUploadedRef.current = false
      startMediaRecorder().catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Microphone access denied')
      })
    }, 60 * 1000)
    return () => { if (part2PrepTimerRef.current) clearTimeout(part2PrepTimerRef.current) }
  }, [status, question, startRecording, startMediaRecorder, setError])

  function handleStart() {
    reset(); resetAudioBlob(); hasUploadedRef.current = false; pendingStopRef.current = false
    if (!question) return
    startPreparing(questionId, partMaxSeconds(question.part))
  }

  function handleStop() {
    if (status === 'recording') {
      if (isRecording) {
        stopRecording()
      } else {
        // MediaRecorder is still initialising (getUserMedia pending).
        // Defer the stop — the effect above will call stopRecording() the
        // moment isRecording transitions to true.
        pendingStopRef.current = true
      }
    } else if (status === 'preparing') {
      if (part2PrepTimerRef.current) clearTimeout(part2PrepTimerRef.current)
      startRecording(); hasUploadedRef.current = false; startMediaRecorder().catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Microphone access denied')
      })
    }
  }

  function handleRetry() { reset() }

  // Sort attempts: chronological (oldest first)
  const sortedAttempts = attempts
    ? [...attempts].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
    : []

  // Determine which attempt is "active" (expanded): explicit selection, or default to latest ready
  const activeAttemptId = selectedAttemptId
    ?? [...sortedAttempts].reverse().find((a: Attempt) => a.status === 'ready')?.id
    ?? null

  return (
    <div className="flex flex-col lg:flex-row h-screen overflow-hidden gap-0">
      {/* ── Left column: practice area ── */}
      <div className="w-full lg:flex-1 flex flex-col h-full relative overflow-hidden">
        {/* Header / breadcrumb */}
        <header className="h-14 flex items-center px-6 border-b border-white/5 text-sm text-gray-400 gap-2 shrink-0">
          <Link to="/" className="hover:text-gray-200 transition-colors">Home</Link>
          <span className="text-[10px]">/</span>
          {question && (
            <>
              <Link to={partRoute(question.part)} className="hover:text-gray-200 transition-colors">
                {partLabel(question.part)}
              </Link>
              <span className="text-[10px]">/</span>
            </>
          )}
          <span className="text-white font-medium line-clamp-1">
            {question?.text ?? 'Loading...'}
          </span>
        </header>

        {/* Scrollable content */}
        <main className="flex-1 overflow-y-auto p-6 pb-24 space-y-4">
          {/* Question card */}
          {questionLoading ? (
            <div className="bg-card rounded-xl p-6 animate-pulse border border-cardBorder">
              <div className="h-4 w-24 bg-background rounded mb-4" />
              <div className="h-6 bg-background rounded" />
            </div>
          ) : questionError ? (
            <div className="bg-card border border-red-500/30 rounded-xl p-6 text-center">
              <p className="text-red-400 font-medium">Could not load question</p>
              <p className="text-gray-400 text-sm mt-1">Check that the backend is running.</p>
            </div>
          ) : question ? (
            <div className="bg-card border border-cardBorder rounded-xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs bg-teal-500/10 text-teal-400 border border-teal-500/30 px-2 py-0.5 rounded-full">
                  {partLabel(question.part)}
                </span>
                {question.category && (
                  <span className="text-xs bg-white/5 text-gray-400 border border-white/10 px-2 py-0.5 rounded-full capitalize">
                    {question.category}
                  </span>
                )}
              </div>
              <div className="flex items-start gap-3">
                <button
                  onClick={() => { playQuestionTTS().catch((err: unknown) => { console.error('Question TTS failed:', err) }) }}
                  className={`w-9 h-9 shrink-0 rounded-full flex items-center justify-center border transition-colors mt-0.5 ${
                    ttsPlaying
                      ? 'bg-teal-500/20 border-teal-500/50'
                      : 'bg-white/5 border-white/10 hover:bg-white/10'
                  }`}
                  title="Listen to question"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className={`h-4 w-4 ${ttsPlaying ? 'text-teal-400 animate-pulse' : 'text-gray-300'}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                    <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
                    <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
                  </svg>
                </button>
                <h1 className="text-textPrimary font-semibold text-lg leading-snug flex-1">
                  {question.text}
                </h1>
              </div>
              {question.bullet_points && question.bullet_points.length > 0 && (
                <ul className="mt-4 space-y-2">
                  {question.bullet_points.map((bp, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-gray-400">
                      <span className="text-teal-400 mt-0.5">•</span>
                      <span>{bp}</span>
                    </li>
                  ))}
                </ul>
              )}
              <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between">
                <p className="text-gray-500 text-xs">Max: {partMaxSeconds(question.part)}s</p>
                <p className="text-gray-500 text-xs">
                  {sortedAttempts.length} {sortedAttempts.length === 1 ? 'attempt' : 'attempts'}
                </p>
              </div>
            </div>
          ) : null}

          {/* Attempt cards */}
          {sortedAttempts.length === 0 && status !== 'polling' && status !== 'uploading' ? (
            <div className="bg-card/50 border border-dashed border-white/10 rounded-xl p-8 text-center">
              <p className="text-gray-400 text-sm">No attempts yet</p>
              <p className="text-gray-500 text-xs mt-1">Press &ldquo;Record&rdquo; below to start</p>
            </div>
          ) : (
            <div className="space-y-4">
              {sortedAttempts.map((attempt, i) =>
                attempt.id === activeAttemptId ? (
                  <ActiveAttemptCard
                    key={attempt.id}
                    attempt={attempt}
                    index={i}
                    isNew={attempt.id === newestAttemptId}
                    shownPronunIds={shownPronunIds}
                    onShowPronunciation={(a) => {
                      if (shownPronunIds.has(a.id)) return
                      setShownPronunIds((prev) => new Set(prev).add(a.id))
                      setPronunAttempt(a)
                    }}
                  />
                ) : (
                  <PrevAttemptCard
                    key={attempt.id}
                    attempt={attempt}
                    index={i}
                    isNew={attempt.id === newestAttemptId}
                    onSelect={() => setSelectedAttemptId(attempt.id)}
                  />
                ),
              )}
            </div>
          )}

          {/* Mobile: Show AI Panel toggle */}
          <div className="lg:hidden">
            <button
              type="button"
              onClick={() => setShowPanel((v) => !v)}
              className="w-full py-2.5 rounded-xl border border-white/10 bg-white/5 text-sm text-gray-300 hover:bg-white/10 transition-colors"
            >
              {showPanel ? 'Hide AI Panel' : 'Show AI Panel'}
            </button>
          </div>

          {/* Mobile: inline AI panel (visible when toggled) */}
          {showPanel && (
            <div className="lg:hidden rounded-xl border border-white/10 overflow-hidden" style={{ minHeight: '480px' }}>
              <RightPanel
                question={question ?? null}
                pronunAttempt={pronunAttempt}
                allQuestions={allQuestions}
              />
            </div>
          )}
        </main>

        {/* Recording bar */}
        <RecordingBar
          status={status}
          elapsed={elapsedSeconds}
          max={maxSeconds}
          onStart={handleStart}
          onStop={handleStop}
          onRetry={handleRetry}
          errorMessage={errorMessage}
          backendStatus={polledAttempt?.status ?? null}
        />
      </div>

      {/* ── Right column: always visible on lg+ ── */}
      <div className="hidden lg:block lg:w-[40%] h-full shrink-0">
        <RightPanel
          question={question ?? null}
          pronunAttempt={pronunAttempt}
          allQuestions={allQuestions}
        />
      </div>
    </div>
  )
}
