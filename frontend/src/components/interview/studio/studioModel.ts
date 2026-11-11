import type {
  InterviewFollowUpInput,
  InterviewGlossaryTerm,
  InterviewKeyPoint,
  InterviewKeyPointInput,
  InterviewLevel,
  InterviewMisconceptionInput,
  InterviewPackDetail,
  InterviewPackInput,
  InterviewQuestion,
  InterviewQuestionInput,
  InterviewRole,
} from '../../../types/interview'
import { LLM_TIMEOUT_MS } from '../../../api/interview'
import { LEVEL_LABELS, ROLE_LABELS, WEIGHT_LABELS, apiErrorDetail, apiErrorStatus, plural } from '../utils'

export { plural }

export type StudioTab = 'details' | 'sources' | 'draft' | 'questions' | 'glossary' | 'export'
export type KeyPointWeight = InterviewKeyPointInput['weight']
export type QuoteStatus = 'none' | 'verified' | 'unverified' | 'pending'

export const ROLE_OPTIONS = (Object.keys(ROLE_LABELS) as InterviewRole[]).map((value) => ({
  value,
  label: ROLE_LABELS[value],
}))

export const LEVEL_OPTIONS = (Object.keys(LEVEL_LABELS) as InterviewLevel[]).map((value) => ({
  value,
  label: LEVEL_LABELS[value],
}))

export const WEIGHT_OPTIONS = ([3, 2, 1] as const).map((value) => ({ value, label: WEIGHT_LABELS[value] }))

export const ANSWER_SECONDS_MIN = 15
export const ANSWER_SECONDS_MAX = 600
export const MAX_KEY_POINTS = 20
export const MAX_MISCONCEPTIONS = 20
export const MAX_FOLLOW_UPS = 10
export const MAX_ALIASES = 20
export const MAX_SOURCE_CHARS = 200_000
export const MAX_DRAFT_SOURCES = 20

export function newUid(): string {
  const crypto = globalThis.crypto
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  // randomUUID only exists in secure contexts; the UI can also be opened over plain http on the LAN
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

function sameJson(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b)
}

export function withoutKey<T>(record: Record<number, T>, key: number): Record<number, T> {
  const next = { ...record }
  delete next[key]
  return next
}

export function packToInput(pack: InterviewPackDetail): InterviewPackInput {
  return {
    title: pack.title,
    role: pack.role,
    level: pack.level,
    job_description: pack.job_description,
    author: pack.author,
  }
}

export function toPackPayload(input: InterviewPackInput): InterviewPackInput {
  return {
    title: input.title.trim(),
    role: input.role,
    level: input.level,
    job_description: input.job_description.trim(),
    author: input.author.trim(),
  }
}

export function isPackInputDirty(form: InterviewPackInput | null, pack: InterviewPackDetail): boolean {
  return form !== null && !sameJson(toPackPayload(form), toPackPayload(packToInput(pack)))
}

export function newKeyPointInput(): InterviewKeyPointInput {
  return { uid: newUid(), text: '', weight: 2, source_quote: null, approved: true }
}

export function newMisconceptionInput(): InterviewMisconceptionInput {
  return { uid: newUid(), text: '', correction: '' }
}

export function newFollowUpInput(): InterviewFollowUpInput {
  return {
    uid: newUid(),
    text: '',
    answer_seconds: 90,
    trigger_key_point_uid: null,
    key_points: [newKeyPointInput()],
    misconceptions: [],
  }
}

export function newQuestionInput(topic = ''): InterviewQuestionInput {
  return {
    topic,
    kind: 'technical',
    text: '',
    answer_seconds: 120,
    key_points: [newKeyPointInput()],
    misconceptions: [],
    follow_ups: [],
  }
}

function keyPointToInput(keyPoint: InterviewKeyPoint): InterviewKeyPointInput {
  return {
    uid: keyPoint.uid,
    text: keyPoint.text,
    weight: keyPoint.weight,
    source_quote: keyPoint.source_quote,
    approved: keyPoint.approved,
  }
}

export function questionToInput(question: InterviewQuestion): InterviewQuestionInput {
  return {
    topic: question.topic,
    kind: question.kind,
    text: question.text,
    answer_seconds: question.answer_seconds,
    key_points: question.key_points.map(keyPointToInput),
    misconceptions: question.misconceptions.map(({ uid, text, correction }) => ({ uid, text, correction })),
    follow_ups: question.follow_ups.map((followUp) => ({
      uid: followUp.uid,
      text: followUp.text,
      answer_seconds: followUp.answer_seconds,
      trigger_key_point_uid: followUp.trigger_key_point_uid,
      key_points: followUp.key_points.map(keyPointToInput),
      misconceptions: followUp.misconceptions.map(({ uid, text, correction }) => ({ uid, text, correction })),
    })),
  }
}

function normalizeKeyPoints(keyPoints: InterviewKeyPointInput[]): InterviewKeyPointInput[] {
  return keyPoints
    .map((keyPoint) => ({
      uid: keyPoint.uid ?? null,
      text: keyPoint.text.trim(),
      weight: keyPoint.weight,
      source_quote: keyPoint.source_quote?.trim() || null,
      approved: keyPoint.approved,
    }))
    .filter((keyPoint) => keyPoint.text || keyPoint.source_quote)
}

function normalizeMisconceptions(misconceptions: InterviewMisconceptionInput[]): InterviewMisconceptionInput[] {
  return misconceptions
    .map((item) => ({ uid: item.uid ?? null, text: item.text.trim(), correction: item.correction.trim() }))
    .filter((item) => item.text || item.correction)
}

export function toQuestionPayload(input: InterviewQuestionInput): InterviewQuestionInput {
  const keyPoints = normalizeKeyPoints(input.key_points)
  const keyPointUids = new Set(keyPoints.map((keyPoint) => keyPoint.uid))
  return {
    topic: input.topic.trim(),
    kind: input.kind,
    text: input.text.trim(),
    answer_seconds: input.answer_seconds,
    key_points: keyPoints,
    misconceptions: normalizeMisconceptions(input.misconceptions),
    follow_ups: input.follow_ups.map((followUp) => ({
      uid: followUp.uid ?? null,
      text: followUp.text.trim(),
      answer_seconds: followUp.answer_seconds,
      trigger_key_point_uid:
        followUp.trigger_key_point_uid && keyPointUids.has(followUp.trigger_key_point_uid)
          ? followUp.trigger_key_point_uid
          : null,
      key_points: normalizeKeyPoints(followUp.key_points),
      misconceptions: normalizeMisconceptions(followUp.misconceptions),
    })),
  }
}

export function isQuestionDirty(saved: InterviewQuestion | null, draft: InterviewQuestionInput | undefined): boolean {
  if (!draft) return false
  if (!saved) return true
  return !sameJson(toQuestionPayload(draft), toQuestionPayload(questionToInput(saved)))
}

function validAnswerSeconds(seconds: number): boolean {
  return Number.isInteger(seconds) && seconds >= ANSWER_SECONDS_MIN && seconds <= ANSWER_SECONDS_MAX
}

function itemErrors(
  scope: string,
  keyPoints: InterviewKeyPointInput[],
  misconceptions: InterviewMisconceptionInput[],
): string[] {
  const errors: string[] = []
  if (keyPoints.length > MAX_KEY_POINTS) errors.push(`${scope}: at most ${MAX_KEY_POINTS} key points.`)
  keyPoints.forEach((keyPoint, index) => {
    if (!keyPoint.text.trim() && keyPoint.source_quote?.trim()) {
      errors.push(`${scope}: key point ${index + 1} has a source quote but no text.`)
    }
  })
  if (misconceptions.length > MAX_MISCONCEPTIONS) errors.push(`${scope}: at most ${MAX_MISCONCEPTIONS} misconceptions.`)
  misconceptions.forEach((item, index) => {
    if (!item.text.trim() && item.correction.trim()) {
      errors.push(`${scope}: misconception ${index + 1} has a correction but no statement.`)
    }
  })
  return errors
}

export function questionErrors(input: InterviewQuestionInput): string[] {
  const secondsError = `answer time must be ${ANSWER_SECONDS_MIN}-${ANSWER_SECONDS_MAX} seconds.`
  const errors: string[] = []
  if (!input.text.trim()) errors.push('Question: text is required.')
  if (!validAnswerSeconds(input.answer_seconds)) errors.push(`Question: ${secondsError}`)
  errors.push(...itemErrors('Question', input.key_points, input.misconceptions))
  if (input.follow_ups.length > MAX_FOLLOW_UPS) errors.push(`Question: at most ${MAX_FOLLOW_UPS} follow-ups.`)
  input.follow_ups.forEach((followUp, index) => {
    const scope = `Follow-up ${index + 1}`
    if (!followUp.text.trim()) errors.push(`${scope}: text is required.`)
    if (!validAnswerSeconds(followUp.answer_seconds)) errors.push(`${scope}: ${secondsError}`)
    errors.push(...itemErrors(scope, followUp.key_points, followUp.misconceptions))
  })
  return errors
}

export function countApproved(keyPoints: InterviewKeyPointInput[]): number {
  return keyPoints.filter((keyPoint) => keyPoint.approved && keyPoint.text.trim()).length
}

export function questionWarnings(input: InterviewQuestionInput): string[] {
  const warnings: string[] = []
  if (countApproved(input.key_points) === 0) {
    warnings.push('Question: no approved key points, so answers cannot be graded.')
  }
  input.follow_ups.forEach((followUp, index) => {
    const scope = `Follow-up ${index + 1}`
    if (countApproved(followUp.key_points) === 0) {
      warnings.push(`${scope}: no approved key points, so it is never offered.`)
    }
    const trigger = input.key_points.find(
      (keyPoint) => keyPoint.uid && keyPoint.uid === followUp.trigger_key_point_uid && keyPoint.text.trim(),
    )
    if (trigger && !trigger.approved) {
      warnings.push(`${scope}: its trigger key point is not approved, so it is never offered.`)
    }
  })
  return warnings
}

export function approveAllKeyPoints(keyPoints: InterviewKeyPointInput[]): InterviewKeyPointInput[] {
  return keyPoints.map((keyPoint) => (keyPoint.text.trim() ? { ...keyPoint, approved: true } : keyPoint))
}

export function hasUnapprovedKeyPoints(input: InterviewQuestionInput): boolean {
  const unapproved = (keyPoints: InterviewKeyPointInput[]) =>
    keyPoints.some((keyPoint) => keyPoint.text.trim() && !keyPoint.approved)
  return unapproved(input.key_points) || input.follow_ups.some((followUp) => unapproved(followUp.key_points))
}

export function needsReview(input: InterviewQuestionInput): boolean {
  return countApproved(input.key_points) === 0 || hasUnapprovedKeyPoints(input)
}

export function quoteStatus(keyPoint: InterviewKeyPointInput, saved: InterviewKeyPoint | undefined): QuoteStatus {
  const quote = keyPoint.source_quote?.trim() ?? ''
  if (!quote) return 'none'
  if (!saved || (saved.source_quote ?? '').trim() !== quote) return 'pending'
  if (saved.quote_verified === true) return 'verified'
  if (saved.quote_verified === false) return 'unverified'
  return 'pending'
}

export function keyPointOptionLabel(keyPoint: InterviewKeyPointInput, index: number): string {
  const text = keyPoint.text.trim()
  const short = text.length > 70 ? `${text.slice(0, 67)}...` : text
  return `#${index + 1} ${WEIGHT_LABELS[keyPoint.weight]}: ${short}`
}

export function uniqueTopics(questions: { topic: string }[]): string[] {
  return Array.from(new Set(questions.map((question) => question.topic.trim()).filter(Boolean)))
}

export interface GlossaryRow {
  key: string
  term: string
  aliases: string
}

export function parseAliases(text: string): string[] {
  const seen = new Set<string>()
  const aliases: string[] = []
  for (const part of text.split(',')) {
    const alias = part.trim().replace(/\s+/g, ' ')
    const folded = alias.toLowerCase()
    if (!alias || seen.has(folded)) continue
    seen.add(folded)
    aliases.push(alias)
  }
  return aliases
}

export function glossaryToRows(terms: InterviewGlossaryTerm[]): GlossaryRow[] {
  return terms.map((term, index) => ({ key: `saved-${index}`, term: term.term, aliases: term.aliases.join(', ') }))
}

export function rowsToGlossary(rows: GlossaryRow[]): InterviewGlossaryTerm[] {
  return rows
    .map((row) => ({ term: row.term.trim(), aliases: parseAliases(row.aliases) }))
    .filter((term) => term.term || term.aliases.length > 0)
}

export function glossaryErrors(rows: GlossaryRow[]): string[] {
  const errors: string[] = []
  const seen = new Set<string>()
  rows.forEach((row, index) => {
    const term = row.term.trim()
    const aliases = parseAliases(row.aliases)
    if (!term) {
      if (aliases.length > 0) errors.push(`Row ${index + 1} has aliases but no term.`)
      return
    }
    const folded = term.toLowerCase()
    if (seen.has(folded)) errors.push(`"${term}" is listed more than once.`)
    seen.add(folded)
    if (aliases.length > MAX_ALIASES) errors.push(`"${term}" has more than ${MAX_ALIASES} aliases.`)
  })
  return errors
}

export function isGlossaryDirty(rows: GlossaryRow[] | null, saved: InterviewGlossaryTerm[]): boolean {
  if (rows === null) return false
  const savedTerms = saved.map((term) => ({ term: term.term, aliases: term.aliases }))
  return !sameJson(rowsToGlossary(rows), savedTerms)
}

export const DRAFT_TIMEOUT_MINUTES = Math.round(LLM_TIMEOUT_MS / 60_000)

export function isRateLimitError(error: unknown): boolean {
  return apiErrorStatus(error) === 429
}

export function isTimeoutError(error: unknown): boolean {
  return error instanceof Error && apiErrorStatus(error) === null && error.message.includes('(timeout)')
}

export function describeDraftError(error: unknown): string {
  if (isTimeoutError(error)) {
    return (
      `Drafting took longer than ${DRAFT_TIMEOUT_MINUTES} minutes. The drafts may still be saved and will then ` +
      'appear in the Questions tab, so wait a few minutes before drafting again.'
    )
  }
  return apiErrorDetail(error)
}
