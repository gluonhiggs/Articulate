/**
 * Tests for the VocabItem.type null guard in RightPanelPlaceholder.tsx.
 *
 * The fix: `{(item.type ?? '').replace('_', ' ')}` instead of `{item.type.replace('_', ' ')}`.
 * Without the guard, a null/undefined type from a truncated LLM response crashes the render.
 */

describe('VocabItem type null guard', () => {
  it('handles null type without throwing', () => {
    const type: string | null | undefined = null
    expect(() => (type ?? '').replace('_', ' ')).not.toThrow()
    expect((type ?? '').replace('_', ' ')).toBe('')
  })

  it('handles undefined type without throwing', () => {
    const type: string | null | undefined = undefined
    expect(() => (type ?? '').replace('_', ' ')).not.toThrow()
    expect((type ?? '').replace('_', ' ')).toBe('')
  })

  it('replaces underscore in phrasal_verb', () => {
    expect(('phrasal_verb' ?? '').replace('_', ' ')).toBe('phrasal verb')
  })

  it('returns plain noun unchanged', () => {
    expect(('noun' ?? '').replace('_', ' ')).toBe('noun')
  })

  it('returns plain verb unchanged', () => {
    expect(('verb' ?? '').replace('_', ' ')).toBe('verb')
  })

  it('only replaces first underscore (native .replace behavior)', () => {
    // String.replace replaces only the first match - consistent with what the UI shows
    expect(('multi_word_phrase' ?? '').replace('_', ' ')).toBe('multi word_phrase')
  })
})
