import type {
  CandidateProfile,
  CandidateProfileInput,
  CvFile,
  InterviewAnswer,
  InterviewDraftRequest,
  InterviewGlossaryTerm,
  InterviewPackDetail,
  InterviewPackInput,
  InterviewPackSummary,
  InterviewQuestion,
  InterviewQuestionInput,
  InterviewSource,
  InterviewSourceInput,
} from '../types/interview'
import { apiFetch } from './client'

const API_BASE = '/api/v1'
export const LLM_TIMEOUT_MS = 180_000

function jsonBody(method: string, body: unknown): RequestInit {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
}

export function fetchInterviewPacks(): Promise<InterviewPackSummary[]> {
  return apiFetch<InterviewPackSummary[]>('/interview/packs')
}

export function fetchInterviewPack(packId: number): Promise<InterviewPackDetail> {
  return apiFetch<InterviewPackDetail>(`/interview/packs/${packId}`)
}

export function createInterviewPack(input: InterviewPackInput): Promise<InterviewPackDetail> {
  return apiFetch<InterviewPackDetail>('/interview/packs', jsonBody('POST', input))
}

export function updateInterviewPack(packId: number, input: InterviewPackInput): Promise<InterviewPackDetail> {
  return apiFetch<InterviewPackDetail>(`/interview/packs/${packId}`, jsonBody('PUT', input))
}

export function deleteInterviewPack(packId: number): Promise<void> {
  return apiFetch<void>(`/interview/packs/${packId}`, { method: 'DELETE' })
}

export function importInterviewPack(file: File): Promise<InterviewPackDetail> {
  const formData = new FormData()
  formData.append('file', file)
  return apiFetch<InterviewPackDetail>('/interview/packs/import', {
    method: 'POST',
    body: formData,
    signal: AbortSignal.timeout(60_000),
  })
}

export function interviewPackExportUrl(packId: number): string {
  return `${API_BASE}/interview/packs/${packId}/export`
}

export function interviewPackReportUrl(packId: number): string {
  return `${API_BASE}/interview/packs/${packId}/report`
}

export function replaceInterviewGlossary(packId: number, terms: InterviewGlossaryTerm[]): Promise<InterviewGlossaryTerm[]> {
  return apiFetch<InterviewGlossaryTerm[]>(`/interview/packs/${packId}/glossary`, jsonBody('PUT', terms))
}

export function addInterviewSource(packId: number, input: InterviewSourceInput): Promise<InterviewSource> {
  return apiFetch<InterviewSource>(`/interview/packs/${packId}/sources`, jsonBody('POST', input))
}

export function deleteInterviewSource(packId: number, sourceId: number): Promise<void> {
  return apiFetch<void>(`/interview/packs/${packId}/sources/${sourceId}`, { method: 'DELETE' })
}

export function draftInterviewQuestions(packId: number, request: InterviewDraftRequest): Promise<InterviewQuestion[]> {
  return apiFetch<InterviewQuestion[]>(`/interview/packs/${packId}/draft`, {
    ...jsonBody('POST', request),
    signal: AbortSignal.timeout(LLM_TIMEOUT_MS),
  })
}

export function fetchCandidateProfile(): Promise<CandidateProfile> {
  return apiFetch<CandidateProfile>('/interview/profile')
}

export function saveCandidateProfile(input: CandidateProfileInput): Promise<CandidateProfile> {
  return apiFetch<CandidateProfile>('/interview/profile', jsonBody('PUT', input))
}

export function readCvFile(file: File): Promise<CvFile> {
  const formData = new FormData()
  formData.append('file', file)
  return apiFetch<CvFile>('/interview/profile/cv-file', {
    method: 'POST',
    body: formData,
    signal: AbortSignal.timeout(60_000),
  })
}

export function fetchAboutYou(): Promise<InterviewPackDetail | null> {
  return apiFetch<InterviewPackDetail | null>('/interview/about-you')
}

export function draftIntroductionQuestion(jobPackId: number | null): Promise<InterviewPackDetail> {
  return apiFetch<InterviewPackDetail>('/interview/about-you/introduction', {
    ...jsonBody('POST', { job_pack_id: jobPackId }),
    signal: AbortSignal.timeout(LLM_TIMEOUT_MS),
  })
}

export function createInterviewQuestion(packId: number, input: InterviewQuestionInput): Promise<InterviewQuestion> {
  return apiFetch<InterviewQuestion>(`/interview/packs/${packId}/questions`, jsonBody('POST', input))
}

export function fetchInterviewQuestion(questionId: number): Promise<InterviewQuestion> {
  return apiFetch<InterviewQuestion>(`/interview/questions/${questionId}`)
}

export function updateInterviewQuestion(questionId: number, input: InterviewQuestionInput): Promise<InterviewQuestion> {
  return apiFetch<InterviewQuestion>(`/interview/questions/${questionId}`, jsonBody('PUT', input))
}

export function retireInterviewQuestion(questionId: number): Promise<void> {
  return apiFetch<void>(`/interview/questions/${questionId}`, { method: 'DELETE' })
}

export function interviewQuestionTtsUrl(questionId: number): string {
  return `${API_BASE}/interview/questions/${questionId}/tts`
}

export function fetchInterviewAnswers(questionId: number): Promise<InterviewAnswer[]> {
  return apiFetch<InterviewAnswer[]>(`/interview/questions/${questionId}/answers`)
}

export function submitInterviewAnswer(questionId: number, audioBlob: Blob): Promise<InterviewAnswer> {
  const formData = new FormData()
  formData.append('audio', audioBlob, 'answer.webm')
  return apiFetch<InterviewAnswer>(`/interview/questions/${questionId}/answers`, {
    method: 'POST',
    body: formData,
    signal: AbortSignal.timeout(120_000),
  })
}

export function fetchInterviewAnswer(answerId: number): Promise<InterviewAnswer> {
  return apiFetch<InterviewAnswer>(`/interview/answers/${answerId}`)
}

export function gradeInterviewAnswer(answerId: number, transcript: string): Promise<InterviewAnswer> {
  return apiFetch<InterviewAnswer>(`/interview/answers/${answerId}/grade`, jsonBody('POST', { transcript }))
}

export function improveInterviewSentences(answerId: number): Promise<InterviewAnswer> {
  return apiFetch<InterviewAnswer>(`/interview/answers/${answerId}/sentence-fixes`, {
    method: 'POST',
    signal: AbortSignal.timeout(LLM_TIMEOUT_MS),
  })
}

export function interviewAnswerAudioUrl(answerId: number): string {
  return `${API_BASE}/interview/answers/${answerId}/audio`
}
