import type { Attempt, DashboardData, Part3Group, Question, SystemInfo } from '../types'

const BASE = '/api/v1'

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, options)
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
  formData.append('audio', audioBlob, 'recording.webm')
  return apiFetch<{ id: number; status: string }>(`/attempts/${questionId}`, {
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

// ─── Dashboard ───────────────────────────────────────────────────────────────

export function fetchDashboard(): Promise<DashboardData> {
  return apiFetch<DashboardData>('/dashboard')
}

// ─── System ──────────────────────────────────────────────────────────────────

export function fetchSystemInfo(): Promise<SystemInfo> {
  return apiFetch<SystemInfo>('/system/info')
}
