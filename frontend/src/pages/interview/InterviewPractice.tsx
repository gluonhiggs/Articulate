import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  fetchInterviewAnswer,
  fetchInterviewAnswers,
  fetchInterviewPack,
  fetchInterviewQuestion,
  gradeInterviewAnswer,
  interviewQuestionTtsUrl,
  submitInterviewAnswer,
} from '../../api/interview'
import { AnswerHistory } from '../../components/interview/AnswerHistory'
import { AnswerPanel } from '../../components/interview/AnswerPanel'
import { AnswerRecorder, type RecorderState } from '../../components/interview/AnswerRecorder'
import {
  apiErrorDetail,
  approvedKeyPointCount,
  formatDuration,
  isAnswerInProgress,
  nextTopLevelQuestionId,
  plural,
  topicLabel,
} from '../../components/interview/utils'
import { useBlobAudio } from '../../hooks/useBlobAudio'
import { nextPollingInterval, type PollingStart } from '../../hooks/usePolling'
import { useRecorder } from '../../hooks/useRecorder'
import type {
  InterviewAnswer,
  InterviewAnswerStatus,
  InterviewPackDetail,
  InterviewQuestion,
} from '../../types/interview'

export function InterviewPractice() {
  const { questionId } = useParams<{ questionId: string }>()
  // Keyed so recording, review and polling state never leak into the next question.
  return <PracticeSession key={questionId} questionId={Number(questionId)} />
}

function PracticeSession({ questionId }: { questionId: number }) {
  const queryClient = useQueryClient()
  const validId = !isNaN(questionId)

  const {
    data: question,
    isLoading: questionLoading,
    isError: questionFailed,
    error: questionError,
  } = useQuery<InterviewQuestion>({
    queryKey: ['interview', 'question', questionId],
    queryFn: () => fetchInterviewQuestion(questionId),
    enabled: validId,
  })

  const parentId = question?.parent_question_id ?? null
  const { data: parent } = useQuery<InterviewQuestion>({
    queryKey: ['interview', 'question', parentId],
    queryFn: () => fetchInterviewQuestion(parentId as number),
    enabled: parentId !== null,
  })

  const packId = question?.pack_id ?? null
  const { data: pack } = useQuery<InterviewPackDetail>({
    queryKey: ['interview', 'pack', packId],
    queryFn: () => fetchInterviewPack(packId as number),
    enabled: packId !== null,
  })

  const { data: answers } = useQuery<InterviewAnswer[]>({
    queryKey: ['interview', 'answers', questionId],
    queryFn: () => fetchInterviewAnswers(questionId),
    enabled: validId,
    staleTime: 0,
  })

  const { playing: ttsPlaying, play: playAudio, stop: stopTts } = useBlobAudio()
  const playQuestion = useCallback(() => playAudio(interviewQuestionTtsUrl(questionId)), [playAudio, questionId])
  const questionLoaded = question !== undefined
  useEffect(() => {
    if (!questionLoaded) return
    const timer = setTimeout(() => void playQuestion(), 400)
    return () => clearTimeout(timer)
  }, [questionLoaded, playQuestion])

  const [activeAnswerId, setActiveAnswerId] = useState<number | null>(null)
  const pollStartRef = useRef<PollingStart | null>(null)
  const [timedOutAnswerId, setTimedOutAnswerId] = useState<number | null>(null)
  const pollTimedOut = activeAnswerId !== null && timedOutAnswerId === activeAnswerId

  const showAnswer = useCallback((answerId: number | null) => {
    setActiveAnswerId(answerId)
  }, [])

  const { data: activeAnswer } = useQuery<InterviewAnswer>({
    queryKey: ['interview', 'answer', activeAnswerId],
    queryFn: () => fetchInterviewAnswer(activeAnswerId as number),
    enabled: activeAnswerId !== null,
    staleTime: 0,
    refetchInterval: (query) =>
      activeAnswerId === null
        ? false
        : nextPollingInterval(
            query.state.data?.status,
            pollStartRef,
            (timedOut) => setTimedOutAnswerId(timedOut ? activeAnswerId : null),
            { key: activeAnswerId, isInProgress: isAnswerInProgress },
          ),
    refetchIntervalInBackground: true,
  })

  const activeStatus = activeAnswer?.status
  const previousStatusRef = useRef<InterviewAnswerStatus | undefined>(undefined)
  useEffect(() => {
    const previous = previousStatusRef.current
    previousStatusRef.current = activeStatus
    if (!isAnswerInProgress(previous) || activeStatus === undefined || isAnswerInProgress(activeStatus)) return
    void queryClient.invalidateQueries({ queryKey: ['interview', 'answers', questionId] })
    if (activeStatus === 'graded') {
      void queryClient.invalidateQueries({ queryKey: ['interview', 'packs'] })
      void queryClient.invalidateQueries({ queryKey: ['interview', 'pack'] })
      void queryClient.invalidateQueries({ queryKey: ['interview', 'question', questionId] })
    }
  }, [activeStatus, questionId, queryClient])

  const gradeMutation = useMutation({
    mutationFn: ({ answerId, transcript }: { answerId: number; transcript: string }) =>
      gradeInterviewAnswer(answerId, transcript),
    onSuccess: (answer) => {
      pollStartRef.current = null
      setTimedOutAnswerId(null)
      queryClient.setQueryData(['interview', 'answer', answer.id], answer)
      void queryClient.invalidateQueries({ queryKey: ['interview', 'answers', questionId] })
    },
    onError: (_err, { answerId }) => {
      void queryClient.invalidateQueries({ queryKey: ['interview', 'answer', answerId] })
    },
  })

  const maxSeconds = question?.answer_seconds ?? 120
  const { isRecording, startRecording, stopRecording, audioBlob, resetAudioBlob } = useRecorder(maxSeconds)
  const [recorderState, setRecorderState] = useState<RecorderState>('idle')
  const [recorderError, setRecorderError] = useState<string | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [failedUpload, setFailedUpload] = useState<Blob | null>(null)
  const pendingStopRef = useRef(false)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      stopRecording()
    }
  }, [stopRecording])

  useEffect(() => {
    if (!isRecording) return
    const interval = setInterval(() => setElapsed((s) => Math.min(s + 1, maxSeconds)), 1000)
    return () => clearInterval(interval)
  }, [isRecording, maxSeconds])

  // Stop pressed while getUserMedia was still pending: apply it once the recorder is live.
  useEffect(() => {
    if (isRecording && pendingStopRef.current) {
      pendingStopRef.current = false
      stopRecording()
    }
  }, [isRecording, stopRecording])

  const uploadAnswer = useCallback(
    (blob: Blob) => {
      setRecorderState('uploading')
      setRecorderError(null)
      submitInterviewAnswer(questionId, blob)
        .then((answer) => {
          setFailedUpload(null)
          queryClient.setQueryData(['interview', 'answer', answer.id], answer)
          void queryClient.invalidateQueries({ queryKey: ['interview', 'answers', questionId] })
          setRecorderState('idle')
          showAnswer(answer.id)
        })
        .catch((err: unknown) => {
          setFailedUpload(blob)
          setRecorderState('idle')
          setRecorderError(apiErrorDetail(err))
        })
    },
    [questionId, queryClient, showAnswer],
  )

  useEffect(() => {
    if (!audioBlob || isRecording || recorderState !== 'recording') return
    uploadAnswer(audioBlob)
  }, [audioBlob, isRecording, recorderState, uploadAnswer])

  const autoSelectedRef = useRef(false)
  useEffect(() => {
    if (autoSelectedRef.current || !answers) return
    autoSelectedRef.current = true
    const latest = answers[0]
    if (latest && isAnswerInProgress(latest.status) && activeAnswerId === null && recorderState === 'idle') {
      queryClient.setQueryData(['interview', 'answer', latest.id], latest)
      showAnswer(latest.id)
    }
  }, [answers, activeAnswerId, recorderState, queryClient, showAnswer])

  function handleStart() {
    stopTts()
    resetAudioBlob()
    setFailedUpload(null)
    pendingStopRef.current = false
    setRecorderError(null)
    setElapsed(0)
    setRecorderState('recording')
    startRecording()
      .then(() => {
        // The page can close while the microphone permission prompt is still open.
        if (!mountedRef.current) stopRecording()
      })
      .catch((err: unknown) => {
        setRecorderState('idle')
        setRecorderError(err instanceof Error ? err.message : 'Microphone access denied')
      })
  }

  function handleRetryUpload() {
    if (failedUpload) uploadAnswer(failedUpload)
  }

  function handleStop() {
    if (isRecording) stopRecording()
    else pendingStopRef.current = true
  }

  function handleTryAgain() {
    gradeMutation.reset()
    setRecorderError(null)
    showAnswer(null)
  }

  function handleSelectAnswer(answer: InterviewAnswer) {
    if (recorderState !== 'idle') return
    gradeMutation.reset()
    if (!queryClient.getQueryData(['interview', 'answer', answer.id])) {
      queryClient.setQueryData(['interview', 'answer', answer.id], answer)
    }
    showAnswer(answer.id)
  }

  function handleGrade(transcript: string) {
    if (activeAnswerId !== null) gradeMutation.mutate({ answerId: activeAnswerId, transcript })
  }

  const gradeError =
    gradeMutation.isError && gradeMutation.variables?.answerId === activeAnswerId
      ? apiErrorDetail(gradeMutation.error)
      : null
  const nextQuestionId =
    pack && question ? nextTopLevelQuestionId(pack.questions, question.parent_question_id ?? question.id) : null
  const hasAnswerKey = question ? approvedKeyPointCount(question) > 0 : true

  return (
    <div className="flex flex-col min-h-screen">
      <div className="bg-sidebar border-b border-cardBorder px-6 py-4 sticky top-0 z-10 flex items-center gap-2 text-sm text-textSecondary min-w-0">
        <Link to="/interview" className="hover:text-textPrimary transition-colors shrink-0">
          Interview
        </Link>
        <span className="text-[10px]">/</span>
        {pack && (
          <>
            <Link
              to={`/interview/packs/${pack.id}`}
              className="hover:text-textPrimary transition-colors truncate max-w-[30%]"
            >
              {pack.title}
            </Link>
            <span className="text-[10px]">/</span>
          </>
        )}
        <span className="text-textPrimary font-medium line-clamp-1">
          {question?.text ?? (questionLoading ? 'Loading...' : 'Question')}
        </span>
      </div>

      <div className="p-6 flex-1 space-y-4 max-w-4xl w-full mx-auto">
        {questionLoading ? (
          <div className="bg-card rounded-xl p-6 animate-pulse border border-cardBorder">
            <div className="h-4 w-24 bg-background rounded mb-4" />
            <div className="h-6 bg-background rounded" />
          </div>
        ) : questionFailed || !validId || !question ? (
          <div className="bg-card border border-red-500/30 rounded-xl p-6 text-center">
            <p className="text-red-400 font-medium">Could not load this question</p>
            <p className="text-gray-400 text-sm mt-1">
              {validId ? apiErrorDetail(questionError) : 'Invalid question link.'}
            </p>
            <Link to="/interview" className="inline-block mt-3 text-sm text-accent hover:underline">
              Back to packs
            </Link>
          </div>
        ) : (
          <>
            <div className="bg-card border border-cardBorder rounded-xl p-5">
              <div className="flex flex-wrap items-center gap-2 mb-3">
                <span className="text-xs bg-teal-500/10 text-teal-400 border border-teal-500/30 px-2 py-0.5 rounded-full">
                  {topicLabel(question.topic)}
                </span>
                {question.parent_question_id !== null && (
                  <span className="text-xs bg-purple-500/10 text-purple-300 border border-purple-500/30 px-2 py-0.5 rounded-full">
                    Follow-up
                  </span>
                )}
              </div>
              {question.parent_question_id !== null && parent && (
                <p className="text-sm text-textSecondary mb-3 border-l-2 border-white/10 pl-3">
                  <span className="text-xs uppercase tracking-wider block mb-0.5">Follow-up to</span>
                  {parent.text}
                </p>
              )}
              <div className="flex items-start gap-3">
                <button
                  onClick={() => (ttsPlaying ? stopTts() : void playQuestion())}
                  className={`w-9 h-9 shrink-0 rounded-full flex items-center justify-center border transition-colors mt-0.5 ${
                    ttsPlaying ? 'bg-teal-500/20 border-teal-500/50' : 'bg-white/5 border-white/10 hover:bg-white/10'
                  }`}
                  title={ttsPlaying ? 'Stop' : 'Listen to question'}
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className={`h-4 w-4 ${ttsPlaying ? 'text-teal-400 animate-pulse' : 'text-gray-300'}`}
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                    <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
                    <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
                  </svg>
                </button>
                <h1 className="text-textPrimary font-semibold text-lg leading-snug flex-1 whitespace-pre-line">
                  {question.text}
                </h1>
              </div>
              <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between">
                <p className="text-gray-500 text-xs">Answer time: {formatDuration(question.answer_seconds)}</p>
                {answers && <p className="text-gray-500 text-xs">{plural(answers.length, 'answer')}</p>}
              </div>
            </div>

            {!hasAnswerKey && !question.retired && (
              <div className="rounded-xl border border-amber-500/30 bg-amber-900/20 px-4 py-3">
                <p className="text-amber-400 text-sm">This question has no approved key points yet.</p>
                <p className="text-amber-300/70 text-xs mt-1">
                  Content cannot be graded until the answer key is approved in Pack Studio. Delivery is still measured.
                </p>
              </div>
            )}

            {activeAnswerId === null && question.retired ? (
              <div className="rounded-xl border border-amber-500/30 bg-amber-900/20 px-4 py-3">
                <p className="text-amber-400 text-sm">This question has been retired from the pack.</p>
                <p className="text-amber-300/70 text-xs mt-1">
                  New answers cannot be recorded. Your previous answers are still listed below.
                </p>
              </div>
            ) : activeAnswerId === null ? (
              <AnswerRecorder
                state={recorderState}
                elapsed={elapsed}
                maxSeconds={maxSeconds}
                error={recorderError}
                onStart={handleStart}
                onStop={handleStop}
                onRetryUpload={failedUpload ? handleRetryUpload : undefined}
              />
            ) : (
              <AnswerPanel
                answer={activeAnswer}
                timedOut={pollTimedOut}
                gradeSubmitting={gradeMutation.isPending}
                gradeError={gradeError}
                nextQuestionId={nextQuestionId}
                packId={packId}
                onGrade={handleGrade}
                onTryAgain={handleTryAgain}
              />
            )}

            {answers && answers.length > 0 && (
              <AnswerHistory answers={answers} activeAnswerId={activeAnswerId} onSelect={handleSelectAnswer} />
            )}
          </>
        )}
      </div>
    </div>
  )
}
