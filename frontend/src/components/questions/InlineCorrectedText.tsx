import React from 'react'
import type { ErrorHighlight } from '../../types'
import { cleanWord } from './utils'

export function InlineCorrectedText({
  transcript,
  highlights,
}: {
  transcript: string
  highlights: ErrorHighlight[] | null
}) {
  if (!highlights || highlights.length === 0) {
    return <span>{transcript}</span>
  }

  // Split transcript into tokens (words + whitespace preserved)
  const tokens = transcript.split(/(\s+)/)
  // Build cleaned non-whitespace tokens with their indices for phrase matching
  const wordTokens: { clean: string; idx: number }[] = []
  for (let i = 0; i < tokens.length; i++) {
    if (!/^\s*$/.test(tokens[i])) {
      wordTokens.push({ clean: cleanWord(tokens[i]), idx: i })
    }
  }

  // Sort highlights by phrase length (longer first) so multi-word matches take priority
  const sorted = [...highlights].filter((h) => h.word).sort(
    (a, b) => (b.word?.split(/\s+/).length ?? 0) - (a.word?.split(/\s+/).length ?? 0),
  )

  // Mark which token indices are consumed by a highlight
  const tokenHighlight = new Map<number, { h: ErrorHighlight; isFirst: boolean; span: number }>()

  for (const h of sorted) {
    const phraseWords = h.word!.toLowerCase().split(/\s+/).map((w) => cleanWord(w))
    const phraseLen = phraseWords.length

    // Scan wordTokens for a consecutive match
    for (let wi = 0; wi <= wordTokens.length - phraseLen; wi++) {
      // Skip if any token in this range is already consumed
      const range = wordTokens.slice(wi, wi + phraseLen)
      if (range.some((wt) => tokenHighlight.has(wt.idx))) continue

      const match = range.every((wt, pi) => wt.clean === phraseWords[pi])
      if (match) {
        for (let pi = 0; pi < phraseLen; pi++) {
          tokenHighlight.set(range[pi].idx, { h, isFirst: pi === 0, span: phraseLen })
        }
        break // Only match first occurrence
      }
    }
  }

  // Render tokens
  const result: React.ReactNode[] = []
  for (let i = 0; i < tokens.length; i++) {
    const token = tokens[i]
    if (/^\s*$/.test(token)) {
      result.push(token)
      continue
    }

    const info = tokenHighlight.get(i)
    if (!info) {
      result.push(<span key={i}>{token}</span>)
      continue
    }

    const { h, isFirst } = info
    const correction = h.correction ?? h.suggestion ?? ''
    const tooltip = h.explanation ?? h.suggestion ?? ''

    if (h.type === 'error') {
      result.push(
        <span key={i} title={tooltip}>
          <span className="correction-wrong">{token}</span>
          {/* Show correction after the last word of the phrase */}
          {isFirst && correction && (
            <>
              {' '}
              <span className="correction-right">{correction}</span>
            </>
          )}
        </span>,
      )
    } else {
      result.push(
        <span key={i} className="uncertain-word" title={tooltip}>
          {token}
        </span>,
      )
    }
  }

  return <>{result}</>
}
