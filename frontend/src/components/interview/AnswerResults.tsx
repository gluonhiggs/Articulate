import { Link } from 'react-router-dom'
import type { InterviewAnswer, InterviewKeyPointResult } from '../../types/interview'
import { AnswerAudioButton } from './AnswerAudioButton'
import { DeliveryCard } from './DeliveryCard'
import { ScoreRing } from './ScoreRing'
import { outlineButtonClass } from './ui'
import { bandStyle, INCORRECT_SCORE_CAP, scoreBand, VERDICT_STYLES, WEIGHT_LABELS } from './utils'

function KeyPointRow({ result }: { result: InterviewKeyPointResult }) {
  const verdict = VERDICT_STYLES[result.verdict]
  return (
    <li className={`flex gap-3 rounded-lg border bg-background/60 px-3 py-2.5 ${verdict.border}`}>
      <span className={`w-5 shrink-0 text-center font-bold ${verdict.text}`} title={verdict.label}>
        {verdict.icon}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`text-xs font-medium ${verdict.text}`}>{verdict.label}</span>
          <span className="text-[11px] text-textSecondary border border-white/10 rounded px-1.5 py-0.5">
            {WEIGHT_LABELS[result.weight]}
          </span>
        </div>
        <p className="text-sm text-textPrimary mt-1 leading-snug">{result.text}</p>
        {result.quote && (
          <p className="text-xs text-gray-400 mt-1 italic">you said: &ldquo;{result.quote}&rdquo;</p>
        )}
        {result.reason && <p className="text-xs text-textSecondary mt-1">{result.reason}</p>}
      </div>
    </li>
  )
}

export function AnswerResults({
  answer,
  nextQuestionId,
  packId,
  onTryAgain,
}: {
  answer: InterviewAnswer
  nextQuestionId: number | null
  packId: number | null
  onTryAgain: () => void
}) {
  const content = bandStyle(answer.content_band)
  const deliveryScore = answer.delivery?.score ?? null
  const delivery = bandStyle(scoreBand(deliveryScore))
  const tips = answer.feedback?.content_tips ?? []
  const englishTip = answer.feedback?.english_tip ?? null

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-card border border-cardBorder rounded-xl p-5 flex items-center gap-4">
          <ScoreRing score={answer.content_score} band={answer.content_band} />
          <div className="min-w-0">
            <p className="text-textSecondary text-xs uppercase tracking-wider">Content accuracy</p>
            <p className={`text-lg font-semibold mt-0.5 ${content.text}`}>{content.label}</p>
            {answer.content_band === 'ungraded' || answer.content_score === null ? (
              <p className="text-xs text-textSecondary mt-1">
                {answer.error_message ?? 'This answer was not graded for content.'}
              </p>
            ) : answer.content_band === 'incorrect' ? (
              <p className="text-xs text-textSecondary mt-1">
                The answer states something technically wrong, so it cannot score above {INCORRECT_SCORE_CAP}.
              </p>
            ) : null}
          </div>
        </div>

        <div className="bg-card border border-cardBorder rounded-xl p-5 flex items-center gap-4">
          <ScoreRing score={deliveryScore} band={scoreBand(deliveryScore)} />
          <div className="min-w-0">
            <p className="text-textSecondary text-xs uppercase tracking-wider">English delivery</p>
            <p className={`text-lg font-semibold mt-0.5 ${delivery.text}`}>
              {deliveryScore === null ? 'Not scored' : delivery.label}
            </p>
            <p className="text-xs text-textSecondary mt-1">Pace, pauses, grammar and word variety. Does not affect content.</p>
          </div>
        </div>
      </div>

      {answer.key_point_results.length > 0 && (
        <div className="bg-card border border-cardBorder rounded-xl p-5">
          <p className="text-textPrimary font-semibold text-sm mb-3">Key points</p>
          <ul className="space-y-2">
            {answer.key_point_results.map((result) => (
              <KeyPointRow key={result.uid} result={result} />
            ))}
          </ul>
        </div>
      )}

      {answer.misconceptions_found.length > 0 && (
        <div className="bg-red-900/20 border border-red-500/30 rounded-xl p-5">
          <p className="text-red-400 font-semibold text-sm mb-3">Misconceptions you stated</p>
          <ul className="space-y-3">
            {answer.misconceptions_found.map((m) => (
              <li key={m.uid} className="text-sm">
                <p className="text-red-300">{m.text}</p>
                {m.quote && <p className="text-xs text-red-300/70 italic mt-1">you said: &ldquo;{m.quote}&rdquo;</p>}
                {m.correction && (
                  <p className="text-xs text-gray-300 mt-1">
                    <span className="text-teal-400 font-medium">Correction:</span> {m.correction}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {answer.delivery && <DeliveryCard delivery={answer.delivery} />}

      {(tips.length > 0 || englishTip) && (
        <div className="bg-card border border-cardBorder rounded-xl p-5 space-y-3">
          {tips.length > 0 && (
            <div>
              <p className="text-textPrimary font-semibold text-sm mb-2">How to improve the content</p>
              <ul className="space-y-1.5">
                {tips.map((tip, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-300">
                    <span className="text-teal-400 mt-0.5">{'\u2022'}</span>
                    <span>{tip}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {englishTip && (
            <div>
              <p className="text-textPrimary font-semibold text-sm mb-1">English tip</p>
              <p className="text-sm text-gray-300">{englishTip}</p>
            </div>
          )}
        </div>
      )}

      {answer.transcript && (
        <div className="bg-card/50 border border-white/5 rounded-xl p-5">
          <p className="text-xs text-textSecondary mb-1">
            Graded transcript{answer.transcript_edited ? ' (edited by you)' : ''}
          </p>
          <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-line">{answer.transcript}</p>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <AnswerAudioButton answerId={answer.id} />
        <div className="flex-1" />
        <button onClick={onTryAgain} className={outlineButtonClass}>
          Try again
        </button>
        {answer.next_follow_up_question_id !== null && (
          <Link
            to={`/interview/questions/${answer.next_follow_up_question_id}`}
            className="px-4 py-2 rounded-lg bg-accent/10 text-accent border border-accent/30 text-sm hover:bg-accent/20 transition-colors"
          >
            Answer follow-up
          </Link>
        )}
        {nextQuestionId !== null ? (
          <Link
            to={`/interview/questions/${nextQuestionId}`}
            className="px-5 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-purple-600 text-white font-semibold text-sm hover:opacity-90 transition-opacity"
          >
            Next question
          </Link>
        ) : (
          packId !== null && (
            <Link to={`/interview/packs/${packId}`} className={outlineButtonClass}>
              Back to pack
            </Link>
          )
        )}
      </div>
    </div>
  )
}
