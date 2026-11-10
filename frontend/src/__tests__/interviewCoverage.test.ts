/**
 * The results page leads with the gaps, so the ordering and the headline are load-bearing:
 * a covered point must never sort above a wrong one, and the headline must count core points.
 */

import { byNeed, coverageHeadline, needsWork } from '../components/interview/utils'
import type { InterviewKeyPointResult, KeyPointVerdict } from '../types/interview'

function point(uid: string, verdict: KeyPointVerdict, weight: 1 | 2 | 3): InterviewKeyPointResult {
  return { uid, text: uid, weight, verdict, quote: null, reason: null, verifier_verdict: null }
}

describe('needsWork', () => {
  it.each<[KeyPointVerdict, boolean]>([
    ['covered', false],
    ['partial', true],
    ['missing', true],
    ['incorrect', true],
  ])('%s needs work: %s', (verdict, expected) => {
    expect(needsWork(point('a', verdict, 3))).toBe(expected)
  })
})

describe('byNeed', () => {
  it('puts wrong before missing before partial, and never a covered point first', () => {
    const sorted = [
      point('covered', 'covered', 3),
      point('partial', 'partial', 3),
      point('missing', 'missing', 3),
      point('incorrect', 'incorrect', 3),
    ]
      .sort(byNeed)
      .map((result) => result.uid)

    expect(sorted).toEqual(['incorrect', 'missing', 'partial', 'covered'])
  })

  it('breaks ties by weight, core first', () => {
    const sorted = [point('detail', 'missing', 1), point('core', 'missing', 3), point('supporting', 'missing', 2)]
      .sort(byNeed)
      .map((result) => result.uid)

    expect(sorted).toEqual(['core', 'supporting', 'detail'])
  })
})

describe('coverageHeadline', () => {
  it('counts only core points when the question has them', () => {
    const results = [
      point('a', 'covered', 3),
      point('b', 'covered', 3),
      point('c', 'missing', 3),
      point('d', 'missing', 2),
      point('e', 'missing', 1),
    ]

    expect(coverageHeadline(results)).toBe('2 of 3 core points covered')
  })

  it('reports partial coverage separately, because a partial point is not a covered one', () => {
    const results = [point('a', 'covered', 3), point('b', 'partial', 3), point('c', 'covered', 3)]

    expect(coverageHeadline(results)).toBe('2 of 3 core points covered, 1 partly')
  })

  it('falls back to every point when none is marked core', () => {
    expect(coverageHeadline([point('a', 'covered', 2), point('b', 'missing', 1)])).toBe('1 of 2 points covered')
  })

  it('says nothing when there is nothing to report', () => {
    expect(coverageHeadline([])).toBe('')
  })

  it('keeps the singular readable', () => {
    expect(coverageHeadline([point('a', 'missing', 3)])).toBe('0 of 1 core point covered')
  })
})
