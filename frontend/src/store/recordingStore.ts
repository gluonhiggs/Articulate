import { create } from 'zustand'

export type RecordingStatus =
  | 'idle'
  | 'preparing'
  | 'recording'
  | 'uploading'
  | 'polling'
  | 'done'
  | 'error'

interface RecordingState {
  status: RecordingStatus
  questionId: number | null
  attemptId: number | null
  elapsedSeconds: number
  maxSeconds: number
  errorMessage: string | null

  // Actions
  startPreparing: (questionId: number, maxSeconds: number) => void
  startRecording: () => void
  setUploading: () => void
  setPolling: (attemptId: number) => void
  setDone: () => void
  setError: (msg: string) => void
  reset: () => void
  tickElapsed: () => void
}

export const useRecordingStore = create<RecordingState>((set) => ({
  status: 'idle',
  questionId: null,
  attemptId: null,
  elapsedSeconds: 0,
  maxSeconds: 45,
  errorMessage: null,

  startPreparing: (questionId, maxSeconds) =>
    set({
      status: 'preparing',
      questionId,
      maxSeconds,
      elapsedSeconds: 0,
      attemptId: null,
      errorMessage: null,
    }),

  startRecording: () =>
    set({
      status: 'recording',
      elapsedSeconds: 0,
    }),

  setUploading: () =>
    set({
      status: 'uploading',
    }),

  setPolling: (attemptId) =>
    set({
      status: 'polling',
      attemptId,
    }),

  setDone: () =>
    set({
      status: 'done',
    }),

  setError: (msg) =>
    set({
      status: 'error',
      errorMessage: msg,
    }),

  reset: () =>
    set({
      status: 'idle',
      questionId: null,
      attemptId: null,
      elapsedSeconds: 0,
      maxSeconds: 45,
      errorMessage: null,
    }),

  tickElapsed: () =>
    set((state) => ({
      elapsedSeconds: state.elapsedSeconds + 1,
    })),
}))
