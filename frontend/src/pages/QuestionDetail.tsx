import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchAttemptHistory, fetchQuestion, submitAttempt } from '../api/client'
import { RecordingBar } from '../components/recording/RecordingBar'
import { ScoreBadge } from '../components/questions/ScoreBadge'
import { useRecorder } from '../hooks/useRecorder'
import { usePolling } from '../hooks/usePolling'
import { useRecordingStore } from '../store/recordingStore'
import type { Attempt, ErrorHighlight, Question } from '../types'

// ── Transcript renderer ──────────────────────────────────────────────────────

function TranscriptWithHighlights({
  transcript,
  highlights,
}: {
  transcript: string
  highlights: ErrorHighlight[] | null
}) {
  if (!highlights || highlights.length === 0) {
    return <p className="text-textPrimary text-sm leading-relaxed">{transcript}</p>
  }

  // Build a lookup: word → highlight (case-insensitive)
  const highlightMap = new Map<string, ErrorHighlight>()
  for (const h of highlights) {
    highlightMap.set(h.word.toLowerCase(), h)
  }

  const words = transcript.split(/(\s+)/)

  return (
    <p className="text-textPrimary text-sm leading-relaxed">
      {words.map((token, i) => {
        // Preserve whitespace tokens as-is
        if (/^\s+$/.test(token)) return token

        const clean = token.replace(/[.,!?;:'"()\-]/g, '').toLowerCase()
        const highlight = highlightMap.get(clean)

        if (!highlight) return <span key={i}>{token}</span>

        return (
          <span
            key={i}
            className={highlight.type === 'error' ? 'error-word' : 'uncertain-word'}
            title={highlight.suggestion}
          >
            {token}
          </span>
        )
      })}
    </p>
  )
}

// ── Metric tag ───────────────────────────────────────────────────────────────

function MetricTag({ label, score }: { label: string; score: number | null }) {
  if (score === null) return null

  function tagColor(s: number) {
    if (s >= 7) return 'bg-cyan-500/10 text-cyan-300 border-cyan-500/20'
    if (s >= 6) return 'bg-purple-500/10 text-purple-300 border-purple-500/20'
    if (s >= 5) return 'bg-yellow-500/10 text-yellow-300 border-yellow-500/20'
    return 'bg-red-500/10 text-red-300 border-red-500/20'
  }

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border ${tagColor(score)}`}
    >
      {label}: {score.toFixed(1)}
    </span>
  )
}

// ── Attempt card ─────────────────────────────────────────────────────────────

function AttemptCard({
  attempt,
  isNew,
}: {
  attempt: Attempt
  isNew: boolean
}) {
  const [expanded, setExpanded] = useState(isNew)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const dateStr = new Date(attempt.created_at).toLocaleString('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })

  if (attempt.status === 'processing') {
    return (
      <div className={`bg-card border border-cardBorder rounded-xl p-4 ${isNew ? 'slide-in-top' : ''}`}>
        <div className="flex items-center gap-3">
          <svg
            className="animate-spin h-4 w-4 text-accent"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <p className="text-textSecondary text-sm">Đang xử lý transcript...</p>
        </div>
      </div>
    )
  }

  if (attempt.status === 'failed') {
    return (
      <div className={`bg-card border border-red-500/30 rounded-xl p-4 ${isNew ? 'slide-in-top' : ''}`}>
        <p className="text-red-400 text-sm">Xử lý thất bại — hãy thử ghi âm lại.</p>
      </div>
    )
  }

  return (
    <div
      className={`bg-card border border-cardBorder rounded-xl overflow-hidden transition-all duration-200 hover:border-accent/30 ${isNew ? 'slide-in-top border-accent/30' : ''}`}
    >
      {/* Collapsed header */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-3 p-4 text-left"
      >
        {/* Play button placeholder */}
        <div className="w-8 h-8 rounded-full bg-background border border-cardBorder flex items-center justify-center flex-shrink-0">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-3 w-3 text-textSecondary"
            viewBox="0 0 24 24"
            fill="currentColor"
          >
            <polygon points="5 3 19 12 5 21 5 3" />
          </svg>
        </div>

        {/* Transcript preview */}
        <div className="flex-1 min-w-0">
          <p className="text-textSecondary text-xs">{dateStr}</p>
          <p className="text-textPrimary text-sm line-clamp-1 mt-0.5">
            {attempt.transcript ?? 'No transcript'}
          </p>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <ScoreBadge score={attempt.score} size="sm" />
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className={`h-4 w-4 text-textSecondary transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-4 pb-4 border-t border-cardBorder pt-4">
          {/* Audio player (hidden — no URL yet; placeholder) */}
          <audio ref={audioRef} className="hidden" />

          {/* Metrics */}
          <div className="flex flex-wrap gap-2 mb-4">
            <MetricTag label="Fluency" score={attempt.fluency} />
            <MetricTag label="Vocabulary" score={attempt.vocabulary} />
            <MetricTag label="Grammar" score={attempt.grammar} />
            <MetricTag label="Pronunciation" score={attempt.pronunciation} />
          </div>

          {/* Full transcript */}
          {attempt.transcript && (
            <div className="mb-4">
              <p className="text-textSecondary text-xs font-semibold uppercase tracking-wider mb-2">
                Transcript
              </p>
              <div className="bg-background rounded-lg p-3">
                <TranscriptWithHighlights
                  transcript={attempt.transcript}
                  highlights={attempt.error_highlights}
                />
              </div>
            </div>
          )}

          {/* Feedback */}
          {attempt.feedback_text && (
            <div>
              <p className="text-textSecondary text-xs font-semibold uppercase tracking-wider mb-2">
                Feedback
              </p>
              <div className="bg-background rounded-lg p-3">
                <p className="text-textSecondary text-sm leading-relaxed">{attempt.feedback_text}</p>
              </div>
            </div>
          )}

          {/* Duration */}
          {attempt.duration_seconds !== null && (
            <p className="text-textSecondary text-xs mt-3">
              Duration: {attempt.duration_seconds}s
            </p>
          )}
        </div>
      )}
    </div>
  )
}

// ── Main page ────────────────────────────────────────────────────────────────

function partMaxSeconds(part: string): number {
  if (part === '1') return 45
  if (part === '2') return 120
  return 60
}

function partLabel(part: string): string {
  if (part === '1') return 'Part 1'
  if (part === '2') return 'Part 2'
  if (part === '3') return 'Part 3'
  return 'Custom'
}

function partRoute(part: string): string {
  if (part === '1') return '/practice/part1'
  if (part === '2') return '/practice/part2'
  if (part === '3') return '/practice/part3'
  return '/'
}

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

  // Fetch question
  const { data: question } = useQuery<Question>({
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

  // Recorder hook
  const maxSec = question ? partMaxSeconds(question.part) : 45
  const { isRecording, startRecording: startMediaRecorder, stopRecording, audioBlob } = useRecorder(maxSec)

  // Polling hook
  const polledAttempt = usePolling(attemptId)

  // Track newest attempt id to animate it
  const [newestAttemptId, setNewestAttemptId] = useState<number | null>(null)

  // Timer tick while recording or preparing
  useEffect(() => {
    if (status !== 'recording' && status !== 'preparing') return
    const interval = setInterval(() => tickElapsed(), 1000)
    return () => clearInterval(interval)
  }, [status, tickElapsed])

  // Watch audioBlob — when it appears, upload
  const hasUploadedRef = useRef(false)
  useEffect(() => {
    if (!audioBlob || status !== 'recording') return
    if (hasUploadedRef.current) return
    hasUploadedRef.current = true

    setUploading()
    submitAttempt(questionId, audioBlob)
      .then((res) => {
        setPolling(res.id)
        setNewestAttemptId(res.id)
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Upload failed')
      })
  }, [audioBlob, status, questionId, setUploading, setPolling, setError])

  // Watch polling result — when done, refresh history
  useEffect(() => {
    if (!polledAttempt) return
    if (polledAttempt.status === 'ready' || polledAttempt.status === 'failed') {
      setDone()
      // Invalidate & refetch history
      queryClient.invalidateQueries({ queryKey: ['attempts', 'history', questionId] })
      queryClient.invalidateQueries({ queryKey: ['questions', 'part1'] })
      queryClient.invalidateQueries({ queryKey: ['questions', 'part2'] })
      queryClient.invalidateQueries({ queryKey: ['questions', 'part3'] })
      void refetchAttempts()
    }
  }, [polledAttempt, setDone, queryClient, questionId, refetchAttempts])

  // Auto-transition: preparing → recording for Part 1 & 3 (no prep time)
  useEffect(() => {
    if (status !== 'preparing' || !question) return
    // Part 2 uses countdown; others go straight to recording
    if (question.part !== '2') {
      startRecording()
      hasUploadedRef.current = false
      void startMediaRecorder()
    }
  }, [status, question, startRecording, startMediaRecorder])

  // Part 2 countdown: after 60s of preparing → start recording
  const part2PrepTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => {
    if (status !== 'preparing' || question?.part !== '2') return
    part2PrepTimerRef.current = setTimeout(() => {
      startRecording()
      hasUploadedRef.current = false
      void startMediaRecorder()
    }, 60 * 1000)
    return () => {
      if (part2PrepTimerRef.current) clearTimeout(part2PrepTimerRef.current)
    }
  }, [status, question, startRecording, startMediaRecorder])

  function handleStart() {
    reset()
    hasUploadedRef.current = false
    if (!question) return
    startPreparing(questionId, partMaxSeconds(question.part))
  }

  function handleStop() {
    if (status === 'recording' && isRecording) {
      stopRecording()
      // setUploading will happen via audioBlob effect
    } else if (status === 'preparing') {
      // Skip prep, start recording immediately
      if (part2PrepTimerRef.current) clearTimeout(part2PrepTimerRef.current)
      startRecording()
      hasUploadedRef.current = false
      void startMediaRecorder()
    }
  }

  function handleRetry() {
    reset()
  }

  // Sort attempts: newest first
  const sortedAttempts = attempts
    ? [...attempts].sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      )
    : []

  return (
    <div className="flex flex-col min-h-screen pb-24">
      {/* Header / breadcrumb */}
      <div className="bg-sidebar border-b border-cardBorder px-6 py-4 sticky top-0 z-10">
        <div className="flex items-center gap-2 text-sm">
          <Link to="/" className="text-textSecondary hover:text-textPrimary transition-colors">
            Trang chủ
          </Link>
          <span className="text-textSecondary">/</span>
          {question && (
            <>
              <Link
                to={partRoute(question.part)}
                className="text-textSecondary hover:text-textPrimary transition-colors"
              >
                {partLabel(question.part)}
              </Link>
              <span className="text-textSecondary">/</span>
            </>
          )}
          <span className="text-textPrimary font-medium line-clamp-1">
            {question?.text ?? 'Loading...'}
          </span>
        </div>
      </div>

      <div className="p-6 max-w-3xl mx-auto w-full flex-1">
        {/* Question card */}
        {question && (
          <div className="bg-card border border-cardBorder rounded-xl p-6 mb-6">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs bg-accent/10 text-accent border border-accent/20 px-2 py-0.5 rounded-full">
                {partLabel(question.part)}
              </span>
              {question.category && (
                <span className="text-xs bg-background text-textSecondary border border-cardBorder px-2 py-0.5 rounded-full capitalize">
                  {question.category}
                </span>
              )}
            </div>

            <h1 className="text-textPrimary font-semibold text-lg leading-snug">
              {question.text}
            </h1>

            {question.bullet_points && question.bullet_points.length > 0 && (
              <ul className="mt-4 space-y-2">
                {question.bullet_points.map((bp, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-textSecondary">
                    <span className="text-accent mt-0.5 flex-shrink-0">•</span>
                    <span>{bp}</span>
                  </li>
                ))}
              </ul>
            )}

            <div className="mt-4 pt-4 border-t border-cardBorder flex items-center justify-between">
              <p className="text-textSecondary text-xs">
                Max: {partMaxSeconds(question.part)}s recording
              </p>
              {question.latest_score !== null && (
                <div className="flex items-center gap-2">
                  <span className="text-textSecondary text-xs">Best score:</span>
                  <ScoreBadge score={question.latest_score} size="sm" />
                </div>
              )}
            </div>
          </div>
        )}

        {/* Attempt history */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <p className="text-textSecondary text-xs font-semibold uppercase tracking-wider">
              Lịch sử luyện tập
            </p>
            <p className="text-textSecondary text-xs">
              {sortedAttempts.length} lần
            </p>
          </div>

          {sortedAttempts.length === 0 && status !== 'polling' && status !== 'uploading' ? (
            <div className="bg-card border border-dashed border-cardBorder rounded-xl p-8 text-center">
              <p className="text-textSecondary text-sm">Chưa có lần luyện tập nào</p>
              <p className="text-textSecondary text-xs mt-1">Nhấn "Ghi âm ngay" để bắt đầu</p>
            </div>
          ) : (
            <div className="space-y-3">
              {/* Show a processing card while we wait for the first result */}
              {(status === 'uploading' || status === 'polling') &&
                newestAttemptId !== null &&
                !sortedAttempts.some((a) => a.id === newestAttemptId) && (
                  <div className="bg-card border border-accent/30 rounded-xl p-4 slide-in-top">
                    <div className="flex items-center gap-3">
                      <svg
                        className="animate-spin h-4 w-4 text-accent"
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                      >
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                        />
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                        />
                      </svg>
                      <p className="text-textSecondary text-sm">AI đang phân tích câu trả lời của bạn...</p>
                    </div>
                  </div>
                )}

              {sortedAttempts.map((attempt) => (
                <AttemptCard
                  key={attempt.id}
                  attempt={attempt}
                  isNew={attempt.id === newestAttemptId}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Recording bar */}
      <RecordingBar
        status={status}
        elapsed={elapsedSeconds}
        max={maxSeconds}
        onStart={handleStart}
        onStop={handleStop}
        onRetry={handleRetry}
        errorMessage={errorMessage}
      />
    </div>
  )
}
