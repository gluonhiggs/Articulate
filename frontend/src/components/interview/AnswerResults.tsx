import { Link } from 'react-router-dom'
import type { InterviewAnswer, InterviewKeyPointResult } from '../../types/interview'
import { AnswerAudioButton } from './AnswerAudioButton'
import { DeliveryDetails, deliverySummary } from './DeliveryCard'
import { Disclosure } from './Disclosure'
import { HighlightedTranscript } from './HighlightedTranscript'
import { ScoreRing } from './ScoreRing'
import { SentenceFixes, sentenceFixSummary } from './SentenceFixes'
import { outlineButtonClass } from './ui'
import {
  bandStyle,
  byNeed,
  countWords,
  coverageHeadline,
  INCORRECT_SCORE_CAP,
  needsWork,
  plural,
  scoreBand,
  VERDICT_STYLES,
  WEIGHT_LABELS,
} from './utils'

function KeyPointRow({ result }: { result: InterviewKeyPointResult }) {
  const verdict = VERDICT_STYLES[result.verdict]
  // A reason for a missing point only restates the point, so it earns no line.
  const reason = result.verdict === 'missing' ? null : result.reason

  return (
    <li className={`flex gap-3 rounded-lg border bg-background/40 px-4 py-3 ${verdict.border}`}>
      <span className={`mt-0.5 w-4 shrink-0 text-center font-bold ${verdict.text}`} title={verdict.label}>
        {verdict.icon}
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-textPrimary leading-snug">{result.text}</p>
        <p className="text-[11px] mt-1.5">
          <span className={`font-medium ${verdict.text}`}>{verdict.label}</span>
          <span className="text-gray-500">
            {' · '}
            {WEIGHT_LABELS[result.weight]}
          </span>
        </p>
        {result.quote && (
          <p className="mt-2 border-l-2 border-white/10 pl-2.5 text-xs text-gray-400">
            <span className="text-gray-500">you said </span>
            <span className="italic">&ldquo;{result.quote}&rdquo;</span>
          </p>
        )}
        {reason && <p className="text-xs text-textSecondary mt-2">{reason}</p>}
      </div>
    </li>
  )
}

function FocusItem({ text, tag }: { text: string; tag?: string }) {
  return (
    <li className="flex items-start gap-2.5 text-sm text-gray-200">
      <span className="text-accent mt-0.5 shrink-0">{'→'}</span>
      <span>
        {tag && <span className="text-[10px] uppercase tracking-wider text-accent/70 mr-1.5">{tag}</span>}
        {text}
      </span>
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
  const results = answer.key_point_results
  const gaps = results.filter(needsWork).sort(byNeed)
  const covered = results.filter((result) => !needsWork(result))
  const ungraded = answer.content_band === 'ungraded' || answer.content_score === null

  return (
    <div className="space-y-3">
      <div className="bg-card border border-cardBorder rounded-xl p-5">
        <div className="flex items-center gap-5">
          <ScoreRing score={answer.content_score} band={answer.content_band} />
          <div className="min-w-0">
            <p className="text-textSecondary text-[11px] uppercase tracking-wider">Content accuracy</p>
            <p className={`text-2xl font-semibold leading-tight mt-0.5 ${content.text}`}>{content.label}</p>
            <p className="text-sm text-textSecondary mt-1">
              {ungraded
                ? (answer.error_message ?? 'This answer was not graded for content.')
                : coverageHeadline(results)}
            </p>
            {answer.content_band === 'incorrect' && (
              <p className="text-xs text-red-400/90 mt-1.5">
                Something stated is technically wrong, which caps the score at {INCORRECT_SCORE_CAP}.
              </p>
            )}
          </div>
        </div>

        <div className="mt-4 pt-3 border-t border-white/5 flex items-baseline gap-2.5">
          <span className={`text-base font-semibold ${delivery.text}`}>{deliveryScore ?? '--'}</span>
          <span className="text-sm text-textSecondary">
            English delivery
            {deliveryScore !== null && ` · ${delivery.label}`}
          </span>
          <span className="ml-auto text-[11px] text-gray-500 shrink-0">does not affect content</span>
        </div>
      </div>

      {answer.misconceptions_found.length > 0 && (
        <div className="bg-red-900/20 border border-red-500/30 rounded-xl p-5">
          <p className="text-red-400 font-semibold text-sm mb-3">Fix this first</p>
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

      {(tips.length > 0 || englishTip) && (
        <div className="rounded-xl border border-accent/25 bg-accent/5 p-5">
          <p className="text-accent font-semibold text-sm mb-2.5">Say this next time</p>
          <ul className="space-y-2">
            {tips.map((tip, i) => (
              <FocusItem key={i} text={tip} />
            ))}
            {englishTip && <FocusItem text={englishTip} tag="Structure" />}
          </ul>
        </div>
      )}

      {results.length > 0 && (
        <section className="space-y-2">
          <div className="flex items-baseline gap-2 px-1 pt-2">
            <h2 className="text-textPrimary font-semibold text-sm">Answer key</h2>
            <span className="text-xs text-textSecondary">{plural(results.length, 'point')}</span>
          </div>
          {gaps.length > 0 && (
            <ul className="space-y-2">
              {gaps.map((result) => (
                <KeyPointRow key={result.uid} result={result} />
              ))}
            </ul>
          )}
          {covered.length > 0 && (
            <Disclosure title={`${covered.length} covered`} summary="what you already got right">
              <ul className="space-y-2">
                {covered.map((result) => (
                  <KeyPointRow key={result.uid} result={result} />
                ))}
              </ul>
            </Disclosure>
          )}
        </section>
      )}

      {answer.sentence_fixes.length > 0 && (
        <Disclosure title="Sentence by sentence" summary={sentenceFixSummary(answer.sentence_fixes)}>
          <SentenceFixes answer={answer} />
        </Disclosure>
      )}

      {answer.delivery && (
        <Disclosure title="English delivery details" summary={deliverySummary(answer.delivery)}>
          <DeliveryDetails delivery={answer.delivery} />
        </Disclosure>
      )}

      {answer.transcript && (
        <Disclosure
          title={answer.transcript_edited ? 'Graded transcript (edited by you)' : 'Graded transcript'}
          summary={plural(countWords(answer.transcript), 'word')}
        >
          <HighlightedTranscript text={answer.transcript} issues={answer.delivery?.grammar_issues ?? []} />
        </Disclosure>
      )}

      <div className="flex flex-wrap items-center gap-2 pt-2">
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
