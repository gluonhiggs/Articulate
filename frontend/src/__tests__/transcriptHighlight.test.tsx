/**
 * The transcript now asserts "you said this wrong" with a strike-through, so the markup
 * matters: a struck word must carry its fix when one exists, and must never be struck
 * for a word the backend could not place.
 */

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { HighlightedTranscript } from '../components/interview/HighlightedTranscript'
import type { InterviewGrammarIssue } from '../types/interview'

const TRANSCRIPT = 'right away it make a plan optimize the instruction from the code'

function issue(overrides: Partial<InterviewGrammarIssue> = {}): InterviewGrammarIssue {
  return {
    text: 'make',
    message: 'After "it", use the third-person verb form "makes".',
    replacements: ['makes'],
    offset: TRANSCRIPT.indexOf('make'),
    ...overrides,
  }
}

function markup(issues: InterviewGrammarIssue[], text = TRANSCRIPT): string {
  return renderToStaticMarkup(<HighlightedTranscript text={text} issues={issues} />)
}

describe('HighlightedTranscript', () => {
  it('strikes the wrong word and shows the fix beside it', () => {
    const html = markup([issue()])
    expect(html).toContain('<span class="correction-wrong">make</span>')
    expect(html).toContain('<span class="correction-right">makes</span>')
  })

  it('strikes the wrong word with no fix when LanguageTool offers none', () => {
    const html = markup([issue({ replacements: [] })])
    expect(html).toContain('<span class="correction-wrong">make</span>')
    expect(html).not.toContain('correction-right')
  })

  it('shows one fix, not every alternative, to keep the sentence readable', () => {
    const html = markup([issue({ replacements: ['makes', 'made', 'making'] })])
    expect(html).toContain('>makes</span>')
    expect(html).not.toContain('made')
    expect(html).not.toContain('making')
  })

  it('carries the reason on hover', () => {
    expect(markup([issue()])).toContain('title="After &quot;it&quot;, use the third-person verb form &quot;makes&quot;."')
  })

  it('keeps the words around the mistake intact', () => {
    const html = markup([issue()])
    expect(html).toContain('right away it')
    expect(html).toContain('a plan optimize the instruction from the code')
  })

  it('marks nothing and explains nothing when no issue could be placed', () => {
    const html = markup([issue({ offset: null })])
    expect(html).not.toContain('correction-wrong')
    expect(html).not.toContain('Hover')
    expect(html).toContain(TRANSCRIPT)
  })

  it('marks every placed mistake in one transcript', () => {
    const text = 'it make a plan and it can fastened the processor'
    const html = markup(
      [
        issue({ text: 'make', offset: text.indexOf('make') }),
        issue({ text: 'fastened', offset: text.indexOf('fastened'), replacements: ['fasten'] }),
      ],
      text,
    )
    expect(html).toContain('<span class="correction-wrong">make</span>')
    expect(html).toContain('<span class="correction-wrong">fastened</span>')
    expect(html).toContain('<span class="correction-right">fasten</span>')
  })
})
