import type {
  ContentBand,
  InterviewAnswerStatus,
  InterviewKeyPointResult,
  InterviewGlossaryCorrection,
  InterviewLevel,
  InterviewQuestion,
  InterviewRole,
  KeyPointVerdict,
} from '../../types/interview'

export const MIN_GRADED_WORDS = 15
export const MIN_DELIVERY_WORDS = 20
export const STRONG_MIN_SCORE = 70
export const DEVELOPING_MIN_SCORE = 40
export const INCORRECT_SCORE_CAP = 39

export const ROLE_LABELS: Record<InterviewRole, string> = {
  swe: 'Software Engineer',
  be: 'Backend Engineer',
  fe: 'Frontend Engineer',
  de: 'Data Engineer',
  da: 'Data Analyst',
  ds: 'Data Scientist',
  other: 'Other role',
}

export const LEVEL_LABELS: Record<InterviewLevel, string> = {
  junior: 'Junior',
  mid: 'Mid-level',
  senior: 'Senior',
}

export const WEIGHT_LABELS: Record<1 | 2 | 3, string> = {
  3: 'Core',
  2: 'Supporting',
  1: 'Detail',
}

export interface ToneStyle {
  label: string
  text: string
  stroke: string
  bar: string
  badge: string
}

const BAND_STYLES: Record<ContentBand, ToneStyle> = {
  strong: {
    label: 'Strong',
    text: 'text-teal-400',
    stroke: 'stroke-teal-400',
    bar: 'bg-teal-400',
    badge: 'bg-teal-500/10 text-teal-400 border-teal-500/30',
  },
  developing: {
    label: 'Developing',
    text: 'text-yellow-400',
    stroke: 'stroke-yellow-400',
    bar: 'bg-yellow-400',
    badge: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
  },
  weak: {
    label: 'Weak',
    text: 'text-orange-400',
    stroke: 'stroke-orange-400',
    bar: 'bg-orange-400',
    badge: 'bg-orange-500/10 text-orange-400 border-orange-500/30',
  },
  incorrect: {
    label: 'Incorrect',
    text: 'text-red-400',
    stroke: 'stroke-red-400',
    bar: 'bg-red-400',
    badge: 'bg-red-500/10 text-red-400 border-red-500/30',
  },
  ungraded: {
    label: 'Not graded',
    text: 'text-gray-400',
    stroke: 'stroke-gray-500',
    bar: 'bg-gray-500',
    badge: 'bg-white/5 text-gray-400 border-white/10',
  },
}

export function bandStyle(band: ContentBand | null): ToneStyle {
  return BAND_STYLES[band ?? 'ungraded']
}

export function scoreBand(score: number | null): ContentBand {
  if (score === null) return 'ungraded'
  if (score >= STRONG_MIN_SCORE) return 'strong'
  if (score >= DEVELOPING_MIN_SCORE) return 'developing'
  return 'weak'
}

export const VERDICT_STYLES: Record<KeyPointVerdict, { label: string; icon: string; text: string; border: string }> = {
  covered: { label: 'Covered', icon: '\u2713', text: 'text-teal-400', border: 'border-teal-500/30' },
  partial: { label: 'Partial', icon: '\u25D0', text: 'text-yellow-400', border: 'border-yellow-500/30' },
  missing: { label: 'Missing', icon: '\u2013', text: 'text-gray-400', border: 'border-white/10' },
  incorrect: { label: 'Incorrect', icon: '\u2717', text: 'text-red-400', border: 'border-red-500/30' },
}

// Worst first, so the rows a candidate must act on are never below the ones they got right.
const VERDICT_NEED: Record<KeyPointVerdict, number> = { incorrect: 0, missing: 1, partial: 2, covered: 3 }

export function needsWork(result: InterviewKeyPointResult): boolean {
  return result.verdict !== 'covered'
}

export function byNeed(a: InterviewKeyPointResult, b: InterviewKeyPointResult): number {
  return VERDICT_NEED[a.verdict] - VERDICT_NEED[b.verdict] || b.weight - a.weight
}

// The headline the score alone cannot give: what share of the points that matter was reached.
export function coverageHeadline(results: InterviewKeyPointResult[]): string {
  if (results.length === 0) return ''
  const core = results.filter((r) => r.weight === 3)
  const scope = core.length > 0 ? core : results
  const noun = core.length > 0 ? 'core point' : 'point'
  const covered = scope.filter((r) => r.verdict === 'covered').length
  const partial = scope.filter((r) => r.verdict === 'partial').length
  const headline = `${covered} of ${plural(scope.length, noun)} covered`
  return partial > 0 ? `${headline}, ${partial} partly` : headline
}

export const ANSWER_STATUS_LABELS: Record<InterviewAnswerStatus, string> = {
  processing: 'Processing',
  transcribing: 'Transcribing',
  needs_review: 'Needs review',
  grading: 'Grading',
  graded: 'Graded',
  pending_quota: 'Waiting for quota',
  'failed:transcription': 'Transcription failed',
  'failed:empty_audio': 'No speech detected',
  'failed:grading': 'Grading failed',
}

const IN_PROGRESS_STATUSES: InterviewAnswerStatus[] = ['processing', 'transcribing', 'grading']

export function isAnswerInProgress(status: InterviewAnswerStatus | undefined): boolean {
  return status !== undefined && IN_PROGRESS_STATUSES.includes(status)
}

// LanguageTool explains the rule as well as the fix; the list only needs the fix,
// and the full message stays available on hover.
export function firstSentence(message: string): string {
  const end = message.search(/[.!?](\s|$)/)
  return end === -1 ? message : message.slice(0, end + 1)
}

export function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? '' : 's'}`
}

export function topicLabel(topic: string): string {
  return topic.trim() || 'General'
}

export function groupByTopic<T extends { topic: string }>(items: T[]): { topic: string; items: T[] }[] {
  const groups = new Map<string, T[]>()
  for (const item of items) {
    const topic = topicLabel(item.topic)
    const group = groups.get(topic)
    if (group) group.push(item)
    else groups.set(topic, [item])
  }
  return Array.from(groups, ([topic, grouped]) => ({ topic, items: grouped }))
}

export function approvedKeyPointCount(question: InterviewQuestion): number {
  return question.key_points.filter((kp) => kp.approved).length
}

// Pages list questions grouped by topic, so practice follows that order rather than the stored positions.
export function displayOrder(questions: InterviewQuestion[]): InterviewQuestion[] {
  return groupByTopic(questions).flatMap((group) => group.items)
}

export function pickPracticeQuestion(questions: InterviewQuestion[]): InterviewQuestion | null {
  const ordered = displayOrder(questions)
  const gradable = ordered.filter((q) => approvedKeyPointCount(q) > 0)
  const pool = gradable.length > 0 ? gradable : ordered
  if (pool.length === 0) return null
  const unanswered = pool.find((q) => q.answer_count === 0)
  if (unanswered) return unanswered
  // Answered but never scored (too short, failed, waiting for quota) needs practice more than any scored one.
  const rank = (q: InterviewQuestion) => q.latest_content_score ?? -1
  return pool.reduce((best, q) => (rank(q) < rank(best) ? q : best))
}

export function nextTopLevelQuestionId(questions: InterviewQuestion[], currentId: number): number | null {
  const ordered = displayOrder(questions)
  const index = ordered.findIndex((q) => q.id === currentId)
  if (index === -1 || index + 1 >= ordered.length) return null
  return ordered[index + 1].id
}

export function countWords(text: string): number {
  return text.split(/\s+/).filter(Boolean).length
}

// The backend stores naive UTC datetimes; without an offset the browser would read them as local time.
export function parseServerDate(value: string): Date {
  return new Date(/(Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}Z`)
}

export function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  return `${Math.floor(total / 60)}:${(total % 60).toString().padStart(2, '0')}`
}

function isWordChar(ch: string | undefined): boolean {
  return ch !== undefined && /[A-Za-z0-9]/.test(ch)
}

export function suggestedOffset(corrections: InterviewGlossaryCorrection[], index: number): number {
  const target = corrections[index]
  return corrections.reduce(
    (offset, c) => (c.start < target.start ? offset + c.replacement.length - (c.end - c.start) : offset),
    target.start,
  )
}

// Correction offsets refer to the raw ASR text, and the candidate may have edited the transcript since,
// so the replacement nearest to its expected position is the one that gets reverted.
export function undoGlossaryCorrection(
  text: string,
  corrections: InterviewGlossaryCorrection[],
  index: number,
): string | null {
  const { original, replacement } = corrections[index]
  if (!replacement) return null
  const expected = suggestedOffset(corrections, index)
  let best: number | null = null
  for (let pos = text.indexOf(replacement); pos !== -1; pos = text.indexOf(replacement, pos + 1)) {
    const bounded = !isWordChar(text[pos - 1]) && !isWordChar(text[pos + replacement.length])
    if (bounded && (best === null || Math.abs(pos - expected) < Math.abs(best - expected))) best = pos
  }
  if (best === null) return null
  return text.slice(0, best) + original + text.slice(best + replacement.length)
}

function parseErrorDetail(body: string): string | null {
  try {
    const detail: unknown = (JSON.parse(body) as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail.length > 0) {
      return detail
        .map((d: unknown) => (d && typeof d === 'object' && 'msg' in d ? String(d.msg) : String(d)))
        .join('; ')
    }
    return null
  } catch {
    return null
  }
}

const API_ERROR_RE = /^API error (\d+): ([\s\S]*)$/

export function apiErrorStatus(err: unknown): number | null {
  const match = err instanceof Error ? API_ERROR_RE.exec(err.message) : null
  return match ? Number(match[1]) : null
}

export function apiErrorDetail(err: unknown): string {
  if (!(err instanceof Error)) return 'Something went wrong'
  const match = API_ERROR_RE.exec(err.message)
  if (!match) return err.message
  return parseErrorDetail(match[2]) ?? (match[2].trim() || `Request failed (HTTP ${match[1]})`)
}
