import {
  apiErrorDetail,
  apiErrorStatus,
  bandStyle,
  countWords,
  formatDuration,
  groupByTopic,
  isAnswerInProgress,
  nextTopLevelQuestionId,
  parseServerDate,
  pickPracticeQuestion,
  plural,
  scoreBand,
  suggestedOffset,
  undoGlossaryCorrection,
} from '../components/interview/utils'
import { nextPollingInterval, POLLING_INTERVAL_MS, POLLING_TIMEOUT_MS } from '../hooks/usePolling'
import type { InterviewGlossaryCorrection, InterviewQuestion } from '../types/interview'

function makeQuestion(overrides: Partial<InterviewQuestion> & { id: number }): InterviewQuestion {
  return {
    uid: `q-${overrides.id}`,
    pack_id: 1,
    parent_question_id: null,
    trigger_key_point_uid: null,
    topic: 'Spark',
    text: `Question ${overrides.id}`,
    answer_seconds: 120,
    retired: false,
    key_points: [{ id: overrides.id, uid: `kp-${overrides.id}`, text: 'kp', weight: 3, source_quote: null, quote_verified: null, approved: true }],
    misconceptions: [],
    follow_ups: [],
    answer_count: 0,
    latest_content_score: null,
    latest_delivery_score: null,
    ...overrides,
  }
}

describe('band styles', () => {
  it.each([
    ['strong', 'Strong', 'text-teal-400'],
    ['developing', 'Developing', 'text-yellow-400'],
    ['weak', 'Weak', 'text-orange-400'],
    ['incorrect', 'Incorrect', 'text-red-400'],
    ['ungraded', 'Not graded', 'text-gray-400'],
  ] as const)('maps %s to label %s and colour %s', (band, label, text) => {
    expect(bandStyle(band).label).toBe(label)
    expect(bandStyle(band).text).toBe(text)
  })

  it('treats a missing band as ungraded', () => {
    expect(bandStyle(null)).toBe(bandStyle('ungraded'))
  })

  it.each([
    [100, 'strong'],
    [70, 'strong'],
    [69, 'developing'],
    [40, 'developing'],
    [39, 'weak'],
    [0, 'weak'],
    [null, 'ungraded'],
  ] as const)('score %s falls in band %s', (score, band) => {
    expect(scoreBand(score)).toBe(band)
  })
})

describe('undoGlossaryCorrection', () => {
  const raw = 'I use pie spark and data bricks daily'
  const corrections: InterviewGlossaryCorrection[] = [
    { start: 6, end: 15, original: 'pie spark', replacement: 'PySpark' },
    { start: 20, end: 31, original: 'data bricks', replacement: 'Databricks' },
  ]
  const suggested = 'I use PySpark and Databricks daily'

  it('computes where each correction sits in the suggested transcript', () => {
    expect(suggestedOffset(corrections, 0)).toBe(6)
    expect(suggestedOffset(corrections, 1)).toBe(18)
    expect(suggested.slice(18, 28)).toBe('Databricks')
    expect(raw.slice(20, 31)).toBe('data bricks')
  })

  it('restores the original words of one correction', () => {
    expect(undoGlossaryCorrection(suggested, corrections, 1)).toBe('I use PySpark and data bricks daily')
    expect(undoGlossaryCorrection(suggested, corrections, 0)).toBe('I use pie spark and Databricks daily')
  })

  it('still finds the replacement after the text around it was edited', () => {
    const edited = 'Honestly, I use PySpark and Databricks daily'
    expect(undoGlossaryCorrection(edited, corrections, 0)).toBe('Honestly, I use pie spark and Databricks daily')
  })

  it('undoes corrections one after another', () => {
    const first = undoGlossaryCorrection(suggested, corrections, 0)
    expect(first).not.toBeNull()
    expect(undoGlossaryCorrection(first as string, corrections, 1)).toBe(raw)
  })

  it('picks the occurrence nearest to the corrected position', () => {
    const repeated: InterviewGlossaryCorrection[] = [{ start: 18, end: 27, original: 'pie spark', replacement: 'PySpark' }]
    const text = 'PySpark is great; PySpark jobs'
    expect(undoGlossaryCorrection(text, repeated, 0)).toBe('PySpark is great; pie spark jobs')
  })

  it('ignores matches inside a longer word', () => {
    const spark: InterviewGlossaryCorrection[] = [{ start: 0, end: 6, original: 'sparks', replacement: 'Spark' }]
    expect(undoGlossaryCorrection('PySpark only', spark, 0)).toBeNull()
  })

  it('returns null when the replacement was edited away', () => {
    expect(undoGlossaryCorrection('I use Spark and Databricks daily', corrections, 0)).toBeNull()
  })
})

describe('pickPracticeQuestion', () => {
  it('returns null for an empty pack', () => {
    expect(pickPracticeQuestion([])).toBeNull()
  })

  it('prefers the first unanswered question', () => {
    const questions = [
      makeQuestion({ id: 1, answer_count: 2, latest_content_score: 30 }),
      makeQuestion({ id: 2 }),
      makeQuestion({ id: 3 }),
    ]
    expect(pickPracticeQuestion(questions)?.id).toBe(2)
  })

  it('picks the lowest-scoring question when all are answered', () => {
    const questions = [
      makeQuestion({ id: 1, answer_count: 1, latest_content_score: 80 }),
      makeQuestion({ id: 2, answer_count: 1, latest_content_score: 35 }),
      makeQuestion({ id: 3, answer_count: 1, latest_content_score: 60 }),
    ]
    expect(pickPracticeQuestion(questions)?.id).toBe(2)
  })

  it('ranks an answered but unscored question below any score', () => {
    const questions = [
      makeQuestion({ id: 1, answer_count: 1, latest_content_score: 10 }),
      makeQuestion({ id: 2, answer_count: 1, latest_content_score: null }),
    ]
    expect(pickPracticeQuestion(questions)?.id).toBe(2)
  })

  it('skips questions without approved key points while gradable ones exist', () => {
    const questions = [
      makeQuestion({ id: 1, key_points: [] }),
      makeQuestion({ id: 2, answer_count: 1, latest_content_score: 90 }),
    ]
    expect(pickPracticeQuestion(questions)?.id).toBe(2)
  })

  it('falls back to ungradable questions when nothing is gradable', () => {
    const questions = [makeQuestion({ id: 1, key_points: [] })]
    expect(pickPracticeQuestion(questions)?.id).toBe(1)
  })

  it('follows the topic-grouped order the pack page shows', () => {
    const questions = [
      makeQuestion({ id: 1, topic: 'SQL', answer_count: 1, latest_content_score: 50 }),
      makeQuestion({ id: 2, topic: 'Spark' }),
      makeQuestion({ id: 3, topic: 'SQL' }),
    ]
    expect(pickPracticeQuestion(questions)?.id).toBe(3)
  })
})

describe('question navigation and grouping', () => {
  const questions = [
    makeQuestion({ id: 10, topic: 'Spark' }),
    makeQuestion({ id: 11, topic: '' }),
    makeQuestion({ id: 12, topic: 'Spark' }),
  ]

  it('groups by topic in first-seen order with a label for empty topics', () => {
    const groups = groupByTopic(questions)
    expect(groups.map((g) => g.topic)).toEqual(['Spark', 'General'])
    expect(groups[0].items.map((q) => q.id)).toEqual([10, 12])
  })

  it('moves to the next question in topic-grouped order, or null at the end', () => {
    expect(nextTopLevelQuestionId(questions, 10)).toBe(12)
    expect(nextTopLevelQuestionId(questions, 12)).toBe(11)
    expect(nextTopLevelQuestionId(questions, 11)).toBeNull()
    expect(nextTopLevelQuestionId(questions, 99)).toBeNull()
  })
})

describe('answer polling', () => {
  it.each(['processing', 'transcribing', 'grading'] as const)('keeps polling while %s', (status) => {
    const setTimedOut = vi.fn()
    const startRef = { current: { key: 1, at: Date.now() } }
    expect(
      nextPollingInterval(status, startRef, setTimedOut, { key: 1, isInProgress: isAnswerInProgress }),
    ).toBe(POLLING_INTERVAL_MS)
    expect(setTimedOut).not.toHaveBeenCalled()
  })

  it.each(['needs_review', 'graded', 'pending_quota', 'failed:grading'] as const)('stops polling at %s', (status) => {
    const startRef = { current: { key: 1, at: 123 } }
    const setTimedOut = vi.fn()
    expect(
      nextPollingInterval(status, startRef, setTimedOut, { key: 1, isInProgress: isAnswerInProgress }),
    ).toBe(false)
    expect(startRef.current).toBeNull()
    expect(setTimedOut).toHaveBeenCalledWith(false)
  })

  it('does not inherit the previous answer timeout window', () => {
    const startRef = { current: { key: 1, at: Date.now() - POLLING_TIMEOUT_MS - 1 } }
    const setTimedOut = vi.fn()
    expect(
      nextPollingInterval('grading', startRef, setTimedOut, { key: 2, isInProgress: isAnswerInProgress }),
    ).toBe(POLLING_INTERVAL_MS)
    expect(setTimedOut).not.toHaveBeenCalled()
  })
})

describe('apiErrorDetail', () => {
  it('extracts a FastAPI string detail', () => {
    const err = new Error('API error 400: {"detail":"Invalid pack file: format must be articulate-interview-pack"}')
    expect(apiErrorDetail(err)).toBe('Invalid pack file: format must be articulate-interview-pack')
  })

  it('joins validation error messages', () => {
    const err = new Error('API error 422: {"detail":[{"msg":"Field required"},{"msg":"Input too long"}]}')
    expect(apiErrorDetail(err)).toBe('Field required; Input too long')
  })

  it('reads the HTTP status of an API error', () => {
    expect(apiErrorStatus(new Error('API error 429: {"detail":"quota"}'))).toBe(429)
    expect(apiErrorStatus(new Error('Cannot connect to server (timeout).'))).toBeNull()
    expect(apiErrorStatus('boom')).toBeNull()
  })

  it('falls back to the raw body or message', () => {
    expect(apiErrorDetail(new Error('API error 502: Bad Gateway'))).toBe('Bad Gateway')
    expect(apiErrorDetail(new Error('Cannot connect to server.'))).toBe('Cannot connect to server.')
    expect(apiErrorDetail('boom')).toBe('Something went wrong')
  })
})

describe('text helpers', () => {
  it('pluralizes nouns by count', () => {
    expect(plural(1, 'graded answer')).toBe('1 graded answer')
    expect(plural(0, 'answer')).toBe('0 answers')
  })

  it('counts words across whitespace', () => {
    expect(countWords('  one two\nthree  ')).toBe(3)
    expect(countWords('')).toBe(0)
  })

  it('formats durations as m:ss', () => {
    expect(formatDuration(120)).toBe('2:00')
    expect(formatDuration(75)).toBe('1:15')
    expect(formatDuration(9)).toBe('0:09')
  })

  it('reads server timestamps without an offset as UTC', () => {
    const utc = Date.UTC(2026, 8, 17, 16, 7, 55)
    expect(parseServerDate('2026-09-17T16:07:55').getTime()).toBe(utc)
    expect(parseServerDate('2026-09-17T16:07:55.234').getTime()).toBe(utc + 234)
    expect(parseServerDate('2026-09-17T16:07:55Z').getTime()).toBe(utc)
    expect(parseServerDate('2026-09-17T23:07:55+07:00').getTime()).toBe(utc)
  })
})
