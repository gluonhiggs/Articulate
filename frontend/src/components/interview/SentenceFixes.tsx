import { useMutation, useQueryClient } from '@tanstack/react-query'
import { improveInterviewSentences } from '../../api/interview'
import { createLogger, errorData } from '../../lib/log'
import type { InterviewAnswer, InterviewSentenceFix, SentenceReason } from '../../types/interview'
import { apiErrorDetail, plural } from './utils'

const log = createLogger('interview/sentences')

const REASON_LABELS: Record<SentenceReason, string> = {
  run_on: 'very long',
  chained: 'clauses chained',
  grammar: 'grammar',
}

export function sentenceFixSummary(fixes: InterviewSentenceFix[]): string {
  const written = fixes.filter((fix) => fix.improved).length
  const counted = plural(fixes.length, 'sentence')
  return written === fixes.length ? `${counted} rewritten` : `${counted} to tighten`
}

function FixRow({ fix }: { fix: InterviewSentenceFix }) {
  return (
    <li className="rounded-lg border border-white/5 bg-background/40 p-3.5">
      <div className="grid gap-3 md:grid-cols-2 md:gap-4">
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-wider text-gray-500 mb-1.5">You said</p>
          <p className="text-sm text-gray-400 leading-snug">{fix.original}</p>
        </div>
        <div className="min-w-0 md:border-l md:border-white/5 md:pl-4">
          <p className="text-[10px] uppercase tracking-wider text-teal-400/70 mb-1.5">Say instead</p>
          {fix.improved ? (
            <p className="text-sm text-gray-100 leading-snug">{fix.improved}</p>
          ) : (
            <p className="text-sm text-gray-600 leading-snug">not written yet</p>
          )}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5 mt-3">
        {fix.reasons.map((reason) => (
          <span key={reason} className="text-[10px] text-amber-300/80 border border-amber-400/25 rounded px-1.5 py-0.5">
            {REASON_LABELS[reason] ?? reason}
          </span>
        ))}
        {fix.note && <span className="text-[10px] text-gray-500">{fix.note}</span>}
      </div>
    </li>
  )
}

export function SentenceFixes({ answer }: { answer: InterviewAnswer }) {
  const queryClient = useQueryClient()
  const fixes = answer.sentence_fixes
  const unwritten = fixes.filter((fix) => !fix.improved).length

  const mutation = useMutation({
    mutationFn: () => {
      log.info('rewrite start', { answerId: answer.id, sentences: unwritten })
      return improveInterviewSentences(answer.id)
    },
    onSuccess: (updated) => {
      const written = updated.sentence_fixes.filter((fix) => fix.improved).length
      log.info('rewrite done', { answerId: updated.id, written, of: updated.sentence_fixes.length })
      queryClient.setQueryData(['interview', 'answer', updated.id], updated)
    },
    onError: (err) => log.error(`rewrite failed for answer ${answer.id}`, errorData(err)),
  })

  return (
    <div className="space-y-2.5">
      <ul className="space-y-2">
        {fixes.map((fix, i) => (
          <FixRow key={i} fix={fix} />
        ))}
      </ul>
      {unwritten > 0 && (
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="px-4 py-2 rounded-lg bg-accent/10 text-accent border border-accent/30 text-sm hover:bg-accent/20 transition-colors disabled:opacity-50"
          >
            {mutation.isPending ? 'Writing...' : unwritten > 1 ? 'Write better versions' : 'Write a better version'}
          </button>
          <span className="text-[11px] text-gray-500">One free-tier AI call.</span>
        </div>
      )}
      {mutation.isError && <p className="text-xs text-red-400">{apiErrorDetail(mutation.error)}</p>}
    </div>
  )
}
