export interface Question {
  id: number
  part: '1' | '2' | '3' | 'custom'
  category: 'person' | 'object' | 'activity' | 'place' | null
  parent_question_id: number | null
  text: string
  bullet_points: string[] | null
  latest_score: number | null
}

export interface Part3Group {
  parent: Question
  questions: Question[]
}

export interface Attempt {
  id: number
  question_id: number
  transcript: string | null
  score: number | null
  fluency: number | null
  vocabulary: number | null
  grammar: number | null
  pronunciation: number | null
  feedback_text: string | null
  error_highlights: ErrorHighlight[] | null
  duration_seconds: number | null
  status: 'processing' | 'ready' | 'failed'
  created_at: string
}

export interface ErrorHighlight {
  word: string
  type: 'error' | 'uncertain'
  suggestion: string
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
  ollama_model: string
}
