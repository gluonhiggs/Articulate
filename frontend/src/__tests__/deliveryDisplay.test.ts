/**
 * The meters replaced four text tiles, so the colour and the state word are now the
 * whole message: they must agree with each other and with the target zone drawn on the
 * track. A green bar beside the words "too slow" would be worse than the old prose.
 *
 * grammarSpans decides which words get underlined in the transcript; highlighting the
 * wrong words is worse than highlighting none, so the misses are tested too.
 */

import { deliveryMeterSpecs } from '../components/interview/DeliveryMeters'
import { grammarSpans } from '../components/interview/HighlightedTranscript'
import { sentenceFixSummary } from '../components/interview/SentenceFixes'
import { firstSentence } from '../components/interview/utils'
import type { InterviewDelivery, InterviewGrammarIssue, InterviewSentenceFix } from '../types/interview'

function delivery(overrides: Partial<InterviewDelivery> = {}): InterviewDelivery {
  return {
    score: 67,
    words: 97,
    speaking_seconds: 104,
    words_per_minute: 61,
    long_pauses: 3,
    pauses_per_100_words: 3.1,
    grammar_available: true,
    grammar_errors_per_100_words: 1.0,
    grammar_issues: [],
    lexical_diversity: 53,
    components: {},
    ...overrides,
  }
}

function issue(text: string, offset: number | null): InterviewGrammarIssue {
  return { text, message: 'Agreement', replacements: ['he goes'], offset }
}

function spec(d: InterviewDelivery, name: string) {
  const found = deliveryMeterSpecs(d).find((item) => item.name === name)
  if (!found) throw new Error(`no meter named ${name}`)
  return found
}

describe('delivery meters', () => {
  it('names the four metrics in a fixed order', () => {
    expect(deliveryMeterSpecs(delivery()).map((item) => item.name)).toEqual([
      'Speaking rate',
      'Long pauses',
      'Grammar errors',
      'Word variety',
    ])
  })

  it.each([
    [61, 'too slow'],
    [100, 'too slow'],
    [145, 'comfortable'],
    [120, 'comfortable'],
    [170, 'comfortable'],
    [200, 'too fast'],
  ])('reads %s words per minute as "%s"', (wpm, word) => {
    const rate = spec(delivery({ words_per_minute: wpm }), 'Speaking rate')
    const inside = wpm >= rate.zone[0] && wpm <= rate.zone[1]
    expect(inside ? rate.inside : wpm < rate.zone[0] ? rate.below : rate.above).toBe(word)
  })

  it('keeps every target zone inside its own scale, so the band is always drawable', () => {
    for (const item of deliveryMeterSpecs(delivery())) {
      expect(item.zone[0]).toBeLessThan(item.zone[1])
      expect(item.zone[1]).toBeLessThanOrEqual(item.max)
      expect(item.warn[0]).toBeLessThanOrEqual(item.zone[0])
      expect(item.warn[1]).toBeGreaterThanOrEqual(item.zone[1])
    }
  })

  it('treats 3.1 pauses per 100 words as just outside the target', () => {
    const pauses = spec(delivery(), 'Long pauses')
    expect(pauses.value).toBe(3.1)
    expect(pauses.zone[1]).toBe(3)
    expect(pauses.figure).toBe('3.1 / 100 words')
  })

  it('marks grammar as unmeasured rather than perfect when the checker was unavailable', () => {
    const grammar = spec(delivery({ grammar_available: false, grammar_errors_per_100_words: null }), 'Grammar errors')
    expect(grammar.value).toBeNull()
    expect(grammar.figure).toBe('not checked')
  })

  it('shows a dash for a metric the backend could not compute', () => {
    const variety = spec(delivery({ lexical_diversity: null }), 'Word variety')
    expect(variety.value).toBeNull()
    expect(variety.figure).toBe('--')
  })

  it('never shows a research acronym, which a reader cannot decode', () => {
    // Common units (wpm, words) are fine; MTLD and TTR name the algorithm, not the thing measured.
    for (const item of deliveryMeterSpecs(delivery())) {
      for (const text of [item.name, item.figure, item.target, item.hint, item.below, item.above, item.inside]) {
        expect(text).not.toMatch(/MTLD|TTR|lexical diversity/i)
      }
    }
  })

  it('leaves word variety as a bare score, since the scale has no unit', () => {
    expect(spec(delivery(), 'Word variety').figure).toBe('53')
  })

  it('explains every figure on hover, in a full sentence', () => {
    for (const item of deliveryMeterSpecs(delivery())) {
      expect(item.hint.length).toBeGreaterThan(20)
      expect(item.hint).toMatch(/\.$/)
    }
  })
})

describe('grammarSpans', () => {
  const text = 'yesterday he go to work and he go home'

  it('anchors an issue at its offset', () => {
    expect(grammarSpans(text, [issue('he go', 10)])).toEqual([
      { start: 10, end: 15, issue: issue('he go', 10) },
    ])
  })

  it('skips an issue the backend could not place', () => {
    expect(grammarSpans(text, [issue('he go', null)])).toEqual([])
  })

  it('skips an offset that no longer points at its own phrase', () => {
    // The transcript was edited after the check: offset 0 is "yesterday", not "he go".
    expect(grammarSpans(text, [issue('he go', 0)])).toEqual([])
  })

  it('skips an offset that runs past the end of the transcript', () => {
    expect(grammarSpans(text, [issue('he go', text.length - 2)])).toEqual([])
  })

  it('returns spans in reading order', () => {
    const spans = grammarSpans(text, [issue('he go', 28), issue('he go', 10)])
    expect(spans.map((span) => span.start)).toEqual([10, 28])
  })

  it('drops a span that overlaps one already kept, so no mark nests inside another', () => {
    const spans = grammarSpans(text, [issue('he go', 10), issue('go to', 13)])
    expect(spans.map((span) => span.issue.text)).toEqual(['he go'])
  })
})

describe('firstSentence', () => {
  it('keeps only the rule, not the lecture', () => {
    expect(
      firstSentence(
        'You have used the passive voice repeatedly in nearby sentences. To make your writing clearer, consider active voice.',
      ),
    ).toBe('You have used the passive voice repeatedly in nearby sentences.')
  })

  it('leaves a message with no sentence break alone', () => {
    expect(firstSentence('Agreement error')).toBe('Agreement error')
  })

  it('does not cut at a decimal point or an abbreviation', () => {
    expect(firstSentence('Use 1.5 spaces here')).toBe('Use 1.5 spaces here')
  })
})

describe('sentenceFixSummary', () => {
  function fix(improved: string): InterviewSentenceFix {
    return { original: 'a long spoken sentence', improved, note: '', reasons: ['run_on'] }
  }

  it('counts what is left to do before any rewrite exists', () => {
    expect(sentenceFixSummary([fix(''), fix('')])).toBe('2 sentences to tighten')
  })

  it('reports completion once every sentence has a rewrite', () => {
    expect(sentenceFixSummary([fix('Short now.')])).toBe('1 sentence rewritten')
  })

  it('still counts as unfinished while one rewrite is missing', () => {
    expect(sentenceFixSummary([fix('Short now.'), fix('')])).toBe('2 sentences to tighten')
  })
})
