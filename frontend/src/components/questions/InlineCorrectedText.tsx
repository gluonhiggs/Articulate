import React from 'react'
import type { UsageError } from '../../types'
import { cleanWord } from './utils'

export function InlineCorrectedText({
  transcript,
  highlights,
}: {
  transcript: string
  highlights: UsageError[] | null
}) {
  if (!highlights || highlights.length === 0) {
    return <span>{transcript}</span>
  }

  // The capture group keeps whitespace tokens so the transcript renders unchanged
  const tokens = transcript.split(/(\s+)/)
  // Cleaned word tokens with their index into `tokens`, for phrase matching
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

  // Token index -> the highlight that consumed it
  const tokenHighlight = new Map<number, { h: UsageError; isFirst: boolean; span: number }>()

  for (const h of sorted) {
    const phraseWords = h.word!.toLowerCase().split(/\s+/).map((w) => cleanWord(w))
    const phraseLen = phraseWords.length

    for (let wi = 0; wi <= wordTokens.length - phraseLen; wi++) {
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

    if (h.type === 'mistake') {
      result.push(
        <span key={i} title={tooltip}>
          <span className="correction-wrong">{token}</span>
          {/* Correction is rendered once per phrase, after its first word */}
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
