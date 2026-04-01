export interface Question {
  id: number
  part: '1' | '2' | '3' | 'custom'
  category: 'person' | 'object' | 'activity' | 'place' | null
  parent_question_id: number | null
  text: string
  bullet_points: string[] | null
  latest_score: number | null
  topic_tag?: string | null
  source?: string | null
  last_seen_date?: string | null
}

export interface Part3Group {
  parent: Question
  questions: Question[]
}

export interface Attempt {
  id: number
  question_id: number
  audio_path?: string | null
  transcript: string | null
  score: number | null
  fluency: number | null
  vocabulary: number | null
  grammar: number | null
  pronunciation: number | null
  feedback_text: string | null
  error_highlights: ErrorHighlight[] | null
  duration_seconds: number | null
  status: 'processing' | 'transcribing' | 'scoring' | 'ready' | 'failed' | 'failed:transcription' | 'failed:empty_audio' | 'failed:scoring'
  created_at: string
}

export interface ErrorHighlight {
  word: string
  type: 'error' | 'uncertain'
  correction?: string    // exact replacement word (empty string = redundant word)
  explanation?: string   // brief reason for the correction
  suggestion?: string    // legacy fallback
}

export interface ImproveResponse {
  improved_text: string
  target_band: number
  explanation: string
}

export interface PronunciationWord {
  word: string
  confidence: number
  is_flagged: boolean
}

export interface SampleAnswerResponse {
  sample_answer: string
  key_phrases: string[]
}

export interface VocabItem {
  term: string
  type: string
  definition: string
  example: string
}

export interface TopicVocabResponse {
  vocabulary: VocabItem[]
}

export interface HeatmapEntry {
  date: string
  count: number
  intensity: number
}

export interface DashboardData {
  current_streak: number
  longest_streak: number
  total_attempts: number
  estimated_band: number | null
  heatmap: HeatmapEntry[]
}

export interface SystemInfo {
  profile: string
  whisper_model: string
  whisper_device: string
  llm_model: string
  is_low_accuracy: boolean
  llm_reachable: boolean
}

export interface ForecastEntry {
  topic_tag: string
  count: number
  last_seen_date: string | null
}
