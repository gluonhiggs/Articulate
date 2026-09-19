import { useState } from 'react'
import type { InterviewAnswer } from '../../types/interview'
import { outlineButtonClass } from './ui'
import { countWords, MIN_GRADED_WORDS, undoGlossaryCorrection } from './utils'

type ChipState = 'applied' | 'undone' | 'unavailable'

export function TranscriptReview({
  answer,
  submitting,
  error,
  onSubmit,
  onDiscard,
}: {
  answer: InterviewAnswer
  submitting: boolean
  error: string | null
  onSubmit: (transcript: string) => void
  onDiscard: () => void
}) {
  const suggested = answer.transcript ?? answer.raw_transcript ?? ''
  const corrections = answer.glossary_corrections
  const [text, setText] = useState(suggested)
  const [chipStates, setChipStates] = useState<ChipState[]>(() => corrections.map(() => 'applied'))
  const [showRaw, setShowRaw] = useState(false)

  const wordCount = countWords(text)

  function handleUndo(index: number) {
    const restored = undoGlossaryCorrection(text, corrections, index)
    if (restored !== null) setText(restored)
    setChipStates((prev) => prev.map((s, i) => (i === index ? (restored === null ? 'unavailable' : 'undone') : s)))
  }

  function handleReset() {
    setText(suggested)
    setChipStates(corrections.map(() => 'applied'))
  }

  return (
    <div className="bg-card border border-cardBorder rounded-xl p-5 space-y-4">
      <div>
        <p className="text-textPrimary font-semibold text-sm">Check your transcript</p>
        <p className="text-textSecondary text-xs mt-1 leading-relaxed">
          Fix only words the speech recognizer got wrong, such as misheard technical terms. Do not improve the
          answer itself: content is graded on exactly this text.
        </p>
      </div>

      {corrections.length > 0 && (
        <div>
          <p className="text-xs text-textSecondary mb-2">Technical terms corrected from the pack glossary</p>
          <div className="flex flex-wrap gap-2">
            {corrections.map((c, i) => (
              <span
                key={`${c.start}-${c.end}`}
                className={[
                  'inline-flex items-center gap-2 text-xs rounded-full border px-2.5 py-1',
                  chipStates[i] === 'applied'
                    ? 'bg-teal-500/10 border-teal-500/30 text-teal-300'
                    : 'bg-white/5 border-white/10 text-gray-500',
                ].join(' ')}
              >
                <span className={chipStates[i] === 'applied' ? '' : 'line-through'}>
                  heard &ldquo;{c.original}&rdquo; {'\u2192'} {c.replacement}
                </span>
                {chipStates[i] === 'applied' && (
                  <button onClick={() => handleUndo(i)} className="text-teal-400 hover:text-teal-200 font-medium">
                    Undo
                  </button>
                )}
                {chipStates[i] === 'unavailable' && <span className="text-amber-400/80">edit the text manually</span>}
              </span>
            ))}
          </div>
        </div>
      )}

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={8}
        maxLength={20_000}
        aria-label="Transcript"
        className="w-full bg-background border border-cardBorder rounded-lg px-3 py-2 text-[15px] leading-relaxed text-gray-200 resize-y focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent/50"
      />

      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-textSecondary">
        <span className={wordCount < MIN_GRADED_WORDS ? 'text-amber-400' : ''}>
          {wordCount} words
          {wordCount < MIN_GRADED_WORDS && ` - answers under ${MIN_GRADED_WORDS} words are not graded for content`}
        </span>
        <div className="flex items-center gap-3">
          {text !== suggested && (
            <button onClick={handleReset} className="hover:text-textPrimary transition-colors">
              Reset to suggested
            </button>
          )}
          {answer.raw_transcript && (
            <button onClick={() => setShowRaw((v) => !v)} className="hover:text-textPrimary transition-colors">
              {showRaw ? 'Hide raw transcript' : 'Show raw transcript'}
            </button>
          )}
        </div>
      </div>

      {showRaw && answer.raw_transcript && (
        <div className="bg-background/60 border border-white/5 rounded-lg px-3 py-2">
          <p className="text-[11px] uppercase tracking-wider text-textSecondary mb-1">Raw speech recognition</p>
          <p className="text-sm text-gray-400 leading-relaxed whitespace-pre-line">{answer.raw_transcript}</p>
        </div>
      )}

      {error && <p className="text-red-400 text-sm">{error}</p>}

      <div className="flex flex-wrap items-center justify-end gap-2">
        <button onClick={onDiscard} disabled={submitting} className={outlineButtonClass}>
          Record again
        </button>
        <button
          onClick={() => onSubmit(text)}
          disabled={submitting || !text.trim()}
          className="px-5 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-purple-600 text-white font-semibold text-sm hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? 'Sending...' : 'Grade my answer'}
        </button>
      </div>
    </div>
  )
}
