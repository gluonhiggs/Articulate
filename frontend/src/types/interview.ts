export type InterviewRole = 'swe' | 'be' | 'fe' | 'de' | 'da' | 'ds' | 'other'
export type InterviewLevel = 'junior' | 'mid' | 'senior'
export type KeyPointVerdict = 'covered' | 'partial' | 'missing' | 'incorrect'
export type ContentBand = 'strong' | 'developing' | 'weak' | 'incorrect' | 'ungraded'
export type InterviewAnswerStatus =
  | 'processing'
  | 'transcribing'
  | 'needs_review'
  | 'grading'
  | 'graded'
  | 'pending_quota'
  | 'failed:transcription'
  | 'failed:empty_audio'
  | 'failed:grading'

export interface InterviewPackInput {
  title: string
  role: InterviewRole
  level: InterviewLevel
  job_description: string
  author: string
}

export interface InterviewTopicReadiness {
  topic: string
  question_count: number
  graded_count: number
  average_content_score: number | null
}

export interface InterviewPackSummary {
  id: number
  uid: string
  title: string
  role: InterviewRole
  level: InterviewLevel
  version: number
  author: string
  question_count: number
  answered_question_count: number
  average_content_score: number | null
  updated_at: string
}

export type InterviewQuestionKind = 'technical' | 'behavioural'

export interface InterviewKeyPointInput {
  uid?: string | null
  text: string
  weight: 1 | 2 | 3
  source_quote?: string | null
  approved: boolean
}

export interface InterviewKeyPoint {
  id: number
  uid: string
  text: string
  weight: 1 | 2 | 3
  source_quote: string | null
  quote_verified: boolean | null
  approved: boolean
}

export interface InterviewMisconceptionInput {
  uid?: string | null
  text: string
  correction: string
}

export interface InterviewMisconception {
  id: number
  uid: string
  text: string
  correction: string
}

export interface InterviewFollowUpInput {
  uid?: string | null
  text: string
  answer_seconds: number
  trigger_key_point_uid: string | null
  key_points: InterviewKeyPointInput[]
  misconceptions: InterviewMisconceptionInput[]
}

export interface InterviewQuestionInput {
  topic: string
  kind: InterviewQuestionKind
  text: string
  answer_seconds: number
  key_points: InterviewKeyPointInput[]
  misconceptions: InterviewMisconceptionInput[]
  follow_ups: InterviewFollowUpInput[]
}

export interface InterviewQuestion {
  id: number
  uid: string
  pack_id: number
  parent_question_id: number | null
  trigger_key_point_uid: string | null
  topic: string
  kind: InterviewQuestionKind
  tags: string[]
  text: string
  answer_seconds: number
  retired: boolean
  key_points: InterviewKeyPoint[]
  misconceptions: InterviewMisconception[]
  follow_ups: InterviewQuestion[]
  answer_count: number
  latest_content_score: number | null
  latest_delivery_score: number | null
}

export interface InterviewGlossaryTerm {
  id?: number
  term: string
  aliases: string[]
}

export interface InterviewSourceInput {
  title: string
  url: string | null
  content: string
}

export interface InterviewSource {
  id: number
  uid: string
  title: string
  url: string | null
  content_length: number
  preview: string
}

export interface InterviewPackDetail extends InterviewPackSummary {
  job_description: string
  glossary: InterviewGlossaryTerm[]
  sources: InterviewSource[]
  questions: InterviewQuestion[]
  topics: InterviewTopicReadiness[]
}

export interface InterviewDraftRequest {
  topic: string
  count: number
  source_ids: number[]
}

export interface InterviewGlossaryCorrection {
  start: number
  end: number
  original: string
  replacement: string
}

export interface InterviewKeyPointResult {
  uid: string
  text: string
  weight: 1 | 2 | 3
  verdict: KeyPointVerdict
  quote: string | null
  reason: string | null
  verifier_verdict: string | null
}

export interface InterviewMisconceptionResult {
  uid: string
  text: string
  correction: string
  quote: string | null
  verifier_confirmed: boolean | null
}

export interface InterviewGrammarIssue {
  text: string
  message: string
  replacements: string[]
  // Character offset into `transcript`, or null when the phrase can no longer be found there.
  offset: number | null
}

export type SentenceReason = 'run_on' | 'chained' | 'grammar'

export interface InterviewSentenceFix {
  original: string
  // Empty until the candidate asks for the rewrite.
  improved: string
  note: string
  reasons: SentenceReason[]
}

export interface InterviewDelivery {
  score: number | null
  words: number
  speaking_seconds: number
  words_per_minute: number | null
  long_pauses: number
  pauses_per_100_words: number | null
  grammar_available: boolean
  grammar_errors_per_100_words: number | null
  grammar_issues: InterviewGrammarIssue[]
  lexical_diversity: number | null
  components: Record<string, number>
}

export interface InterviewFeedback {
  content_tips: string[]
  english_tip: string | null
}

export interface InterviewAnswer {
  id: number
  question_id: number
  status: InterviewAnswerStatus
  created_at: string
  graded_at: string | null
  duration_seconds: number | null
  raw_transcript: string | null
  transcript: string | null
  transcript_edited: boolean
  glossary_corrections: InterviewGlossaryCorrection[]
  delivery: InterviewDelivery | null
  content_score: number | null
  content_band: ContentBand | null
  key_point_results: InterviewKeyPointResult[]
  misconceptions_found: InterviewMisconceptionResult[]
  feedback: InterviewFeedback | null
  sentence_fixes: InterviewSentenceFix[]
  next_follow_up_question_id: number | null
  error_message: string | null
}

export interface CandidateProfile {
  full_name: string
  target_role: string
  cv_text: string
  cv_filename: string
  has_cv: boolean
}

export interface CandidateProfileSaved extends CandidateProfile {
  introductions_retired: number
  introduction_written: boolean
}

export interface CandidateProfileInput {
  target_role: string
  cv_text: string
  cv_filename: string
}

export interface CvFile {
  filename: string
  text: string
  characters: number
  truncated: boolean
}

export type SkillState = 'no_questions' | 'weak' | 'unpractised' | 'ready'

export interface SkillRow {
  skill: string
  label: string
  question_count: number
  in_job: boolean
  in_cv: boolean
  best_score: number | null
  answered: number
  state: SkillState
}

export interface SkillList {
  job_pack_id: number | null
  job_title: string | null
  job_skills: string[]
  cv_skills: string[]
  rows: SkillRow[]
}

export interface SkillQuestion {
  id: number
  pack_id: number
  pack_title: string
  topic: string
  kind: InterviewQuestionKind
  text: string
  answer_seconds: number
  tags: string[]
  matched: string[]
  latest_content_score: number | null
}

export interface SkillSet {
  skills: string[]
  labels: string[]
  questions: SkillQuestion[]
}
