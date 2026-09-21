/**
 * The circle, the badge and the criterion tags must colour a band the same way.
 * They used to disagree: 5.0-5.4 was yellow on the detail page and red in the lists,
 * and the tags coloured low scores purple - the badge's colour for band 6+.
 */

import { bandTier, scoreColor, scoreGradient, tagClass } from '../components/questions/utils'

const CASES: [number, string][] = [
  [9, 'high'],
  [7.5, 'high'],
  [7, 'high'],
  [6.9, 'good'],
  [6, 'good'],
  [5.9, 'fair'],
  [5.5, 'fair'],
  [5, 'fair'],
  [4.9, 'low'],
  [4, 'low'],
  [0, 'low'],
]

describe('band colours', () => {
  it.each(CASES)('band %s is the %s tier', (score, tier) => {
    expect(bandTier(score)).toBe(tier)
  })

  it.each(CASES)('every surface agrees on band %s', (score, tier) => {
    expect(tagClass(score)).toBe(`tag-${tier}`)
    const circle = scoreColor(score)
    const gradient = scoreGradient(score)
    const family = { high: ['teal', 'cyan'], good: ['purple'], fair: ['yellow'], low: ['red'] }[tier as 'high']
    expect(family.some((colour) => circle.ring.includes(colour))).toBe(true)
    expect(family.some((colour) => circle.text.includes(colour))).toBe(true)
    expect(family.some((colour) => gradient.includes(colour))).toBe(true)
  })

  it('keeps the glow for the top tier only', () => {
    expect(scoreColor(7).glow).toBe('glow-circle')
    expect(scoreColor(6.9).glow).toBe('')
  })

  it('does not fall back to a shared colour for two different tiers', () => {
    const tiers = ['high', 'good', 'fair', 'low'] as const
    const gradients = new Set(tiers.map((t) => scoreGradient({ high: 9, good: 6, fair: 5, low: 1 }[t])))
    expect(gradients.size).toBe(tiers.length)
  })
})
