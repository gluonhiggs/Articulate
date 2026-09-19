import { POLLING_TIMEOUT_MS } from '../../hooks/usePolling'
import type { InterviewAnswer } from '../../types/interview'
import { AnswerResults } from './AnswerResults'
import { TranscriptReview } from './TranscriptReview'
import { outlineButtonClass } from './ui'
import { isAnswerInProgress } from './utils'

const FAILURE_TITLES: Record<string, string> = {
  'failed:transcription': 'Could not transcribe your recording',
  'failed:empty_audio': 'No speech detected - check your microphone',
  'failed:grading': 'Grading failed',
}

function ProgressCard({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="rounded-xl p-5 glow-border-active bg-card">
      <div className="flex items-center gap-3">
        <div className="animate-spin h-4 w-4 border-2 border-teal-400 border-t-transparent rounded-full" />
        <span className="text-textPrimary text-sm font-medium">{title}</span>
      </div>
      <p className="text-textSecondary text-xs mt-2">{hint}</p>
    </div>
  )
}

function NoticeCard({
  tone,
  title,
  message,
  children,
}: {
  tone: 'warning' | 'error'
  title: string
  message: string | null
  children: React.ReactNode
}) {
  const colors =
    tone === 'warning'
      ? { card: 'bg-amber-900/20 border-amber-500/30', title: 'text-amber-400', text: 'text-amber-300/80' }
      : { card: 'bg-red-900/20 border-red-500/30', title: 'text-red-400', text: 'text-red-300/80' }
  return (
    <div className={`rounded-xl p-5 border ${colors.card}`}>
      <p className={`text-sm font-medium ${colors.title}`}>{title}</p>
      {message && <p className={`text-xs mt-1 leading-relaxed ${colors.text}`}>{message}</p>}
      <div className="mt-4 flex flex-wrap items-center gap-2">{children}</div>
    </div>
  )
}

export function AnswerPanel({
  answer,
  timedOut,
  gradeSubmitting,
  gradeError,
  nextQuestionId,
  packId,
  onGrade,
  onTryAgain,
}: {
  answer: InterviewAnswer | undefined
  timedOut: boolean
  gradeSubmitting: boolean
  gradeError: string | null
  nextQuestionId: number | null
  packId: number | null
  onGrade: (transcript: string) => void
  onTryAgain: () => void
}) {
  if (!answer) return <div className="h-32 bg-card animate-pulse rounded-xl" />

  const tryAgainButton = (
    <button onClick={onTryAgain} className={outlineButtonClass}>
      Try again
    </button>
  )
  const retryGradingButton = (
    <button
      onClick={() => answer.transcript && onGrade(answer.transcript)}
      disabled={gradeSubmitting || !answer.transcript}
      className="px-5 py-2 rounded-lg bg-accent/10 text-accent border border-accent/30 text-sm hover:bg-accent/20 transition-colors disabled:opacity-50"
    >
      {gradeSubmitting ? 'Sending...' : 'Retry grading'}
    </button>
  )

  if (timedOut && isAnswerInProgress(answer.status)) {
    return (
      <NoticeCard
        tone="error"
        title="This is taking too long"
        message={`The answer is still being processed after ${Math.round(POLLING_TIMEOUT_MS / 60_000)} minutes. Make sure the backend is running, then open it again from Previous answers or record a new answer.`}
      >
        {tryAgainButton}
      </NoticeCard>
    )
  }

  switch (answer.status) {
    case 'processing':
    case 'transcribing':
      return (
        <ProgressCard
          title="Transcribing your answer..."
          hint="You will be able to fix misheard words before grading."
        />
      )
    case 'grading':
      return (
        <ProgressCard
          title="Grading your answer..."
          hint="Each key point is checked against your own words, then a second model verifies the claims. This usually takes under a minute."
        />
      )
    case 'needs_review':
      return (
        <TranscriptReview
          key={answer.id}
          answer={answer}
          submitting={gradeSubmitting}
          error={gradeError}
          onSubmit={onGrade}
          onDiscard={onTryAgain}
        />
      )
    case 'graded':
      return (
        <AnswerResults answer={answer} nextQuestionId={nextQuestionId} packId={packId} onTryAgain={onTryAgain} />
      )
    case 'pending_quota':
      return (
        <NoticeCard
          tone="warning"
          title="Free-tier AI quota reached"
          message={
            answer.error_message ??
            'The free AI quota is used up for now. Your transcript is saved, so you can retry grading later.'
          }
        >
          {retryGradingButton}
          {tryAgainButton}
          {gradeError && <p className="w-full text-red-400 text-xs">{gradeError}</p>}
        </NoticeCard>
      )
    default:
      return (
        <NoticeCard tone="error" title={FAILURE_TITLES[answer.status] ?? 'Something went wrong'} message={answer.error_message}>
          {answer.status === 'failed:grading' && retryGradingButton}
          {tryAgainButton}
          {gradeError && <p className="w-full text-red-400 text-xs">{gradeError}</p>}
        </NoticeCard>
      )
  }
}
