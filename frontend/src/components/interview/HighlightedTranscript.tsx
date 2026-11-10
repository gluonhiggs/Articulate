import type { InterviewGrammarIssue } from '../../types/interview'

interface Span {
  start: number
  end: number
  issue: InterviewGrammarIssue
}

/**
 * Issues whose phrase could still be located in this transcript, in reading order and
 * never overlapping. The backend re-anchors each offset against the transcript it
 * returns; an issue it could not place arrives with a null offset and is skipped here
 * rather than highlighting the wrong words.
 */
export function grammarSpans(text: string, issues: InterviewGrammarIssue[]): Span[] {
  const candidates = issues
    .filter((issue) => issue.offset !== null && issue.text.length > 0)
    .map((issue) => ({ start: issue.offset as number, end: (issue.offset as number) + issue.text.length, issue }))
    .filter((span) => span.end <= text.length && text.slice(span.start, span.end) === span.issue.text)
    .sort((a, b) => a.start - b.start || b.end - a.end)

  const spans: Span[] = []
  for (const span of candidates) {
    if (spans.length === 0 || span.start >= spans[spans.length - 1].end) spans.push(span)
  }
  return spans
}

function hint(issue: InterviewGrammarIssue): string {
  const suggestion = issue.replacements.slice(0, 3).join(' / ')
  return suggestion ? `${suggestion} - ${issue.message}` : issue.message
}

export function HighlightedTranscript({
  text,
  issues,
}: {
  text: string
  issues: InterviewGrammarIssue[]
}) {
  const spans = grammarSpans(text, issues)
  if (spans.length === 0) {
    return <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-line">{text}</p>
  }

  const parts: React.ReactNode[] = []
  let cursor = 0
  spans.forEach((span, i) => {
    if (span.start > cursor) parts.push(text.slice(cursor, span.start))
    parts.push(
      <mark
        key={i}
        title={hint(span.issue)}
        className="bg-red-500/10 text-gray-100 rounded-sm px-0.5 underline decoration-wavy decoration-red-400/70 underline-offset-4 cursor-help"
      >
        {text.slice(span.start, span.end)}
      </mark>,
    )
    cursor = span.end
  })
  if (cursor < text.length) parts.push(text.slice(cursor))

  return (
    <>
      <p className="text-sm text-gray-300 leading-loose whitespace-pre-line">{parts}</p>
      <p className="text-[11px] text-gray-500 mt-3">Underlined words carry a grammar note. Hover one to read it.</p>
    </>
  )
}
