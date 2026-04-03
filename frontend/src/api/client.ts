import type { Attempt, DashboardData, ForecastEntry, ImproveResponse, Part3Group, PronunciationWord, Question, SampleAnswerResponse, SystemInfo, TopicVocabResponse } from '../types'

const BASE = '/api/v1'

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, {
      ...options,
      signal: options?.signal ?? AbortSignal.timeout(10_000),
    })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'TimeoutError') {
      throw new Error('Cannot connect to server (timeout). Make sure the backend is running.')
    }
    throw new Error('Cannot connect to server. Make sure the backend is running.')
  }
  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText)
    throw new Error(`API error ${response.status}: ${text}`)
  }
  return response.json() as Promise<T>
}

// ─── Question endpoints ──────────────────────────────────────────────────────

export function fetchPart1Questions(hideAnswered: boolean): Promise<Question[]> {
  const params = new URLSearchParams()
  if (hideAnswered) params.set('hide_answered', 'true')
  const qs = params.toString() ? `?${params.toString()}` : ''
  return apiFetch<Question[]>(`/questions/part1${qs}`)
}

export function fetchPart2Questions(
  category: string | null,
  hideAnswered: boolean,
): Promise<Question[]> {
  const params = new URLSearchParams()
  if (category) params.set('category', category)
  if (hideAnswered) params.set('hide_answered', 'true')
  const qs = params.toString() ? `?${params.toString()}` : ''
  return apiFetch<Question[]>(`/questions/part2${qs}`)
}

export function fetchPart3Questions(
  category: string | null,
  hideAnswered: boolean,
): Promise<Part3Group[]> {
  const params = new URLSearchParams()
  if (category) params.set('category', category)
  if (hideAnswered) params.set('hide_answered', 'true')
  const qs = params.toString() ? `?${params.toString()}` : ''
  return apiFetch<Part3Group[]>(`/questions/part3${qs}`)
}

export function fetchQuestion(id: number): Promise<Question> {
  return apiFetch<Question>(`/questions/${id}`)
}

// ─── Attempt endpoints ───────────────────────────────────────────────────────

export async function submitAttempt(
  questionId: number,
  audioBlob: Blob,
): Promise<{ id: number; status: string }> {
  const formData = new FormData()
  formData.append('question_id', String(questionId))
  formData.append('audio', audioBlob, 'recording.webm')
  return apiFetch<{ id: number; status: string }>('/attempts/submit', {
    method: 'POST',
    body: formData,
  })
}

export function fetchAttemptStatus(attemptId: number): Promise<Attempt> {
  return apiFetch<Attempt>(`/attempts/${attemptId}/status`)
}

export function fetchAttemptHistory(questionId: number): Promise<Attempt[]> {
  return apiFetch<Attempt[]>(`/attempts/history/${questionId}`)
}

export function fetchImprovedVersion(attemptId: number): Promise<ImproveResponse> {
  return apiFetch<ImproveResponse>(`/attempts/${attemptId}/improve`, {
    method: 'POST',
    signal: AbortSignal.timeout(60_000),
  })
}

export function fetchPronunciationDetails(attemptId: number): Promise<{ words: PronunciationWord[] }> {
  return apiFetch<{ words: PronunciationWord[] }>(`/attempts/${attemptId}/pronunciation`)
}

/** Returns the URL to stream attempt audio. Does not fetch — use with Audio or fetch-to-blob. */
export function getAttemptAudioUrl(attemptId: number): string {
  return `${BASE}/attempts/${attemptId}/audio`
}

// ─── AI Assist ──────────────────────────────────────────────────────────────

export function fetchSampleAnswer(questionId: number): Promise<SampleAnswerResponse> {
  return apiFetch<SampleAnswerResponse>(`/questions/${questionId}/sample-answer`, {
    method: 'POST',
    signal: AbortSignal.timeout(60_000),
  })
}

export function fetchTopicVocab(questionId: number): Promise<TopicVocabResponse> {
  return apiFetch<TopicVocabResponse>(`/questions/${questionId}/topic-vocab`, {
    method: 'POST',
    signal: AbortSignal.timeout(60_000),
  })
}

// ─── Dashboard ───────────────────────────────────────────────────────────────

export function fetchDashboard(): Promise<DashboardData> {
  return apiFetch<DashboardData>('/dashboard')
}

// ─── System ──────────────────────────────────────────────────────────────────

export function fetchSystemInfo(): Promise<SystemInfo> {
  return apiFetch<SystemInfo>('/system/info')
}

export function patchLlmModel(model: string): Promise<SystemInfo> {
  return apiFetch<SystemInfo>('/system/model', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model }),
  })
}

export function patchTranscriptionMode(mode: string): Promise<SystemInfo> {
  return apiFetch<SystemInfo>('/system/transcription-mode', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode }),
  })
}

// ─── Forecast ────────────────────────────────────────────────────────────────

export function fetchForecast(): Promise<ForecastEntry[]> {
  return apiFetch<ForecastEntry[]>('/questions/forecast')
}
