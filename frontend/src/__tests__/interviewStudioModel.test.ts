import {
  approveAllKeyPoints,
  describeDraftError,
  glossaryErrors,
  glossaryToRows,
  isGlossaryDirty,
  isPackInputDirty,
  isQuestionDirty,
  isRateLimitError,
  keyPointOptionLabel,
  needsReview,
  newQuestionInput,
  newUid,
  packToInput,
  parseAliases,
  questionErrors,
  questionToInput,
  questionWarnings,
  quoteStatus,
  rowsToGlossary,
  toQuestionPayload,
  uniqueTopics,
  withoutKey,
} from '../components/interview/studio/studioModel'
import type { InterviewKeyPoint, InterviewPackDetail, InterviewQuestion } from '../types/interview'

function keyPoint(overrides: Partial<InterviewKeyPoint> = {}): InterviewKeyPoint {
  return {
    id: 1,
    uid: 'kp-1',
    text: 'Indexes speed up reads',
    weight: 3,
    source_quote: null,
    quote_verified: null,
    approved: true,
    ...overrides,
  }
}

function question(overrides: Partial<InterviewQuestion> = {}): InterviewQuestion {
  return {
    id: 10,
    uid: 'q-10',
    pack_id: 1,
    parent_question_id: null,
    trigger_key_point_uid: null,
    topic: 'Databases',
    text: 'What is an index?',
    answer_seconds: 120,
    retired: false,
    key_points: [keyPoint()],
    misconceptions: [{ id: 5, uid: 'mc-1', text: 'Indexes always help', correction: 'They slow writes' }],
    follow_ups: [],
    answer_count: 2,
    latest_content_score: 55,
    latest_delivery_score: 70,
    ...overrides,
  }
}

function followUp(overrides: Partial<InterviewQuestion> = {}): InterviewQuestion {
  return question({
    id: 11,
    uid: 'fu-1',
    parent_question_id: 10,
    trigger_key_point_uid: 'kp-1',
    text: 'When would you avoid an index?',
    answer_seconds: 90,
    key_points: [keyPoint({ id: 2, uid: 'kp-2', text: 'Write-heavy tables', weight: 2 })],
    misconceptions: [],
    answer_count: 0,
    ...overrides,
  })
}

const pack: InterviewPackDetail = {
  id: 1,
  uid: 'pack-1',
  title: 'Data Engineer pack',
  role: 'de',
  level: 'mid',
  version: 3,
  author: 'Coach',
  question_count: 1,
  answered_question_count: 0,
  average_content_score: null,
  updated_at: '2026-09-17T00:00:00',
  job_description: 'Spark and SQL',
  glossary: [{ id: 1, term: 'PySpark', aliases: ['pie spark'] }],
  sources: [],
  questions: [],
  topics: [],
}

describe('questionToInput', () => {
  it('maps a saved question with follow-ups to the upsert payload shape', () => {
    const input = questionToInput(question({ follow_ups: [followUp()] }))
    expect(input).toEqual({
      topic: 'Databases',
      text: 'What is an index?',
      answer_seconds: 120,
      key_points: [{ uid: 'kp-1', text: 'Indexes speed up reads', weight: 3, source_quote: null, approved: true }],
      misconceptions: [{ uid: 'mc-1', text: 'Indexes always help', correction: 'They slow writes' }],
      follow_ups: [
        {
          uid: 'fu-1',
          text: 'When would you avoid an index?',
          answer_seconds: 90,
          trigger_key_point_uid: 'kp-1',
          key_points: [{ uid: 'kp-2', text: 'Write-heavy tables', weight: 2, source_quote: null, approved: true }],
          misconceptions: [],
        },
      ],
    })
  })
})

describe('toQuestionPayload', () => {
  it('trims text, drops blank rows and turns empty quotes into null', () => {
    const input = questionToInput(question())
    input.text = '  What is an index?  '
    input.key_points.push({ uid: 'blank', text: '   ', weight: 2, source_quote: '  ', approved: true })
    input.key_points[0].source_quote = '   '
    input.misconceptions.push({ uid: 'blank-mc', text: ' ', correction: '' })

    const payload = toQuestionPayload(input)
    expect(payload.text).toBe('What is an index?')
    expect(payload.key_points).toHaveLength(1)
    expect(payload.key_points[0].source_quote).toBeNull()
    expect(payload.misconceptions).toHaveLength(1)
  })

  it('clears a follow-up trigger that points at a removed key point', () => {
    const input = questionToInput(question({ follow_ups: [followUp()] }))
    input.key_points = [{ uid: 'kp-9', text: 'Another point', weight: 3, source_quote: null, approved: true }]
    expect(toQuestionPayload(input).follow_ups[0].trigger_key_point_uid).toBeNull()
  })

  it('keeps a trigger that points at an existing key point', () => {
    const input = questionToInput(question({ follow_ups: [followUp()] }))
    expect(toQuestionPayload(input).follow_ups[0].trigger_key_point_uid).toBe('kp-1')
  })
})

describe('isQuestionDirty', () => {
  it('is clean without a draft or when the draft only differs by whitespace or blank rows', () => {
    const saved = question()
    expect(isQuestionDirty(saved, undefined)).toBe(false)
    const draft = questionToInput(saved)
    draft.text = `${draft.text}  `
    draft.key_points.push({ uid: 'new', text: '', weight: 2, source_quote: null, approved: true })
    expect(isQuestionDirty(saved, draft)).toBe(false)
  })

  it('detects real edits', () => {
    const saved = question()
    const draft = questionToInput(saved)
    draft.key_points[0].approved = false
    expect(isQuestionDirty(saved, draft)).toBe(true)
  })

  it('treats an unsaved new question as dirty', () => {
    expect(isQuestionDirty(null, newQuestionInput())).toBe(true)
  })
})

describe('questionErrors and questionWarnings', () => {
  it('requires question text and a valid answer time', () => {
    const input = newQuestionInput()
    input.answer_seconds = 5
    expect(questionErrors(input)).toEqual(['Question: text is required.', 'Question: answer time must be 15-600 seconds.'])
  })

  it('rejects an empty answer time from a cleared number input', () => {
    const input = questionToInput(question())
    input.answer_seconds = Number.NaN
    expect(questionErrors(input)).toHaveLength(1)
  })

  it('flags quotes without key point text and follow-ups without text', () => {
    const input = questionToInput(question({ follow_ups: [followUp()] }))
    input.key_points.push({ uid: 'x', text: ' ', weight: 2, source_quote: 'quoted', approved: true })
    input.follow_ups[0].text = ''
    expect(questionErrors(input)).toEqual([
      'Question: key point 2 has a source quote but no text.',
      'Follow-up 1: text is required.',
    ])
  })

  it('has no errors for a valid saved question', () => {
    expect(questionErrors(questionToInput(question({ follow_ups: [followUp()] })))).toEqual([])
  })

  it('warns when nothing is approved and when a follow-up can never be offered', () => {
    const input = questionToInput(
      question({
        key_points: [keyPoint({ approved: false })],
        follow_ups: [followUp({ key_points: [keyPoint({ uid: 'kp-2', approved: false })] })],
      }),
    )
    expect(questionWarnings(input)).toEqual([
      'Question: no approved key points, so answers cannot be graded.',
      'Follow-up 1: no approved key points, so it is never offered.',
      'Follow-up 1: its trigger key point is not approved, so it is never offered.',
    ])
  })
})

describe('approval helpers', () => {
  it('approves every key point that has text', () => {
    const approved = approveAllKeyPoints([
      { uid: 'a', text: 'A', weight: 3, source_quote: null, approved: false },
      { uid: 'b', text: '', weight: 2, source_quote: null, approved: false },
    ])
    expect(approved.map((kp) => kp.approved)).toEqual([true, false])
  })

  it('needs review when a follow-up key point is unapproved or nothing is approved', () => {
    expect(needsReview(questionToInput(question()))).toBe(false)
    expect(needsReview(questionToInput(question({ key_points: [] })))).toBe(true)
    const withDraftFollowUp = question({ follow_ups: [followUp({ key_points: [keyPoint({ approved: false })] })] })
    expect(needsReview(questionToInput(withDraftFollowUp))).toBe(true)
  })
})

describe('quoteStatus', () => {
  const draft = { uid: 'kp-1', text: 'x', weight: 3 as const, approved: true }

  it('reports the saved verification only while the quote is unchanged', () => {
    const saved = keyPoint({ source_quote: 'B-tree index', quote_verified: true })
    expect(quoteStatus({ ...draft, source_quote: 'B-tree index' }, saved)).toBe('verified')
    expect(quoteStatus({ ...draft, source_quote: 'B-tree indexes' }, saved)).toBe('pending')
    expect(quoteStatus({ ...draft, source_quote: 'B-tree index' }, { ...saved, quote_verified: false })).toBe('unverified')
  })

  it('has no status without a quote and is pending for new key points', () => {
    expect(quoteStatus({ ...draft, source_quote: '  ' }, undefined)).toBe('none')
    expect(quoteStatus({ ...draft, source_quote: 'quote' }, undefined)).toBe('pending')
  })
})

describe('glossary helpers', () => {
  it('parses comma separated aliases, collapsing spaces and case-insensitive duplicates', () => {
    expect(parseAliases(' post  gres, postgres ,, Postgres ')).toEqual(['post gres', 'postgres'])
    expect(parseAliases('')).toEqual([])
  })

  it('round-trips saved terms and ignores fully blank rows', () => {
    const rows = glossaryToRows(pack.glossary)
    expect(rows[0]).toMatchObject({ term: 'PySpark', aliases: 'pie spark' })
    expect(isGlossaryDirty(null, pack.glossary)).toBe(false)
    expect(isGlossaryDirty([...rows, { key: 'new', term: ' ', aliases: '' }], pack.glossary)).toBe(false)
    expect(rowsToGlossary(rows)).toEqual([{ term: 'PySpark', aliases: ['pie spark'] }])
  })

  it('detects edits', () => {
    const rows = glossaryToRows(pack.glossary)
    rows[0].aliases = 'pie spark, pyspark'
    expect(isGlossaryDirty(rows, pack.glossary)).toBe(true)
  })

  it('rejects aliases without a term and duplicate terms', () => {
    const errors = glossaryErrors([
      { key: 'a', term: 'Databricks', aliases: '' },
      { key: 'b', term: '', aliases: 'data bricks' },
      { key: 'c', term: 'databricks', aliases: '' },
    ])
    expect(errors).toEqual(['Row 2 has aliases but no term.', '"databricks" is listed more than once.'])
  })
})

describe('pack details', () => {
  it('is dirty only when a trimmed field differs', () => {
    expect(isPackInputDirty(null, pack)).toBe(false)
    expect(isPackInputDirty({ ...packToInput(pack), title: ' Data Engineer pack ' }, pack)).toBe(false)
    expect(isPackInputDirty({ ...packToInput(pack), level: 'senior' }, pack)).toBe(true)
  })
})

describe('misc helpers', () => {
  it('generates RFC 4122 v4 uids', () => {
    expect(newUid()).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
  })

  it('labels trigger options with index, weight and shortened text', () => {
    const label = keyPointOptionLabel({ uid: 'a', text: 'x'.repeat(100), weight: 3, approved: true }, 1)
    expect(label.startsWith('#2 Core: ')).toBe(true)
    expect(label.endsWith('...')).toBe(true)
  })

  it('lists distinct non-empty topics in order', () => {
    expect(uniqueTopics([{ topic: 'SQL' }, { topic: ' ' }, { topic: 'Spark' }, { topic: 'SQL ' }])).toEqual(['SQL', 'Spark'])
  })

  it('removes a numeric key without mutating the record', () => {
    const record = { 1: 'a', 2: 'b' }
    expect(withoutKey(record, 1)).toEqual({ 2: 'b' })
    expect(record).toEqual({ 1: 'a', 2: 'b' })
  })

  it('classifies draft errors', () => {
    const quota = new Error('API error 429: {"detail": "Gemini free-tier quota reached, try later"}')
    expect(isRateLimitError(quota)).toBe(true)
    expect(describeDraftError(quota)).toBe('Gemini free-tier quota reached, try later')
    const timeout = new Error('Cannot connect to server (timeout). Make sure the backend is running.')
    expect(isRateLimitError(timeout)).toBe(false)
    expect(describeDraftError(timeout)).toContain('longer than 3 minutes')
    expect(describeDraftError(timeout)).toContain('may still be saved')
  })
})
