import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchSampleAnswer, fetchTopicVocab } from '../../api/client'
import type { Question, SampleAnswerResponse, TopicVocabResponse, VocabItem } from '../../types'
import { partRoute } from '../questions/utils'

export function RightPanelPlaceholder({
  question,
  allQuestions,
}: {
  question: Question | null
  allQuestions: Question[]
}) {
  const navigate = useNavigate()
  const [sampleAnswer, setSampleAnswer] = useState<SampleAnswerResponse | null>(null)
  const [topicVocab, setTopicVocab] = useState<TopicVocabResponse | null>(null)
  const [loading, setLoading] = useState<'sample' | 'vocab' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pronunInput, setPronunInput] = useState('')
  const pronunAudioRef = useRef<HTMLAudioElement | null>(null)
  const [pronunPlaying, setPronunPlaying] = useState(false)

  // Compute prev/next question IDs
  const currentIndex = question ? allQuestions.findIndex((q) => q.id === question.id) : -1
  const prevId = currentIndex > 0 ? allQuestions[currentIndex - 1].id : null
  const nextId = currentIndex < allQuestions.length - 1 && currentIndex >= 0
    ? allQuestions[currentIndex + 1].id
    : null

  // Reset content when question changes
  useEffect(() => {
    setSampleAnswer(null)
    setTopicVocab(null)
    setError(null)
    setLoading(null)
  }, [question?.id])

  function handleSampleAnswer() {
    if (!question) return
    setLoading('sample')
    setError(null)
    fetchSampleAnswer(question.id)
      .then((res) => setSampleAnswer(res))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Failed to generate sample answer'))
      .finally(() => setLoading(null))
  }

  function handleTopicVocab() {
    if (!question) return
    setLoading('vocab')
    setError(null)
    fetchTopicVocab(question.id)
      .then((res) => setTopicVocab(res))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Failed to generate vocabulary'))
      .finally(() => setLoading(null))
  }

  function handlePronunPractice() {
    const word = pronunInput.trim()
    if (!word) return
    if (pronunAudioRef.current) { pronunAudioRef.current.pause(); pronunAudioRef.current = null }
    setPronunPlaying(true)
    fetch(`/api/v1/tts/pronounce?text=${encodeURIComponent(word)}`)
      .then((res) => {
        if (!res.ok) throw new Error(`TTS error: ${res.status}`)
        return res.blob()
      })
      .then((blob) => {
        const audio = new Audio(URL.createObjectURL(blob))
        pronunAudioRef.current = audio
        audio.onended = () => { setPronunPlaying(false); URL.revokeObjectURL(audio.src) }
        audio.onerror = () => { setPronunPlaying(false); URL.revokeObjectURL(audio.src) }
        return audio.play()
      })
      .catch(() => setPronunPlaying(false))
  }

  function handlePrev() {
    if (prevId === null || !question) return
    navigate(partRoute(question.part, prevId))
  }

  function handleNext() {
    if (nextId === null || !question) return
    navigate(partRoute(question.part, nextId))
  }

  const hasContent = sampleAnswer || topicVocab

  return (
    <div className="flex flex-col h-full">
      {/* Tab bar */}
      <div className="flex border-b border-white/10 px-4 pt-2 shrink-0">
        <div className="flex-1 pb-3 text-sm font-medium text-teal-400 border-b-2 border-teal-400 text-center">
          AI Support
        </div>
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-y-auto p-4">
        {loading && (
          <div className="flex items-center justify-center gap-2 py-8">
            <div className="animate-spin h-4 w-4 border-2 border-teal-400 border-t-transparent rounded-full" />
            <span className="text-gray-400 text-sm">
              {loading === 'sample' ? 'Generating sample answer...' : 'Generating vocabulary...'}
            </span>
          </div>
        )}

        {error && !loading && (
          <div className="rounded-lg bg-red-500/10 border border-red-500/20 p-3 mb-4">
            <p className="text-red-400 text-sm">{error}</p>
          </div>
        )}

        {!hasContent && !loading && !error && (
          <div className="flex items-center justify-center h-full">
            <p className="text-gray-600 text-sm italic text-center">
              Click &ldquo;Sample answer&rdquo; or &ldquo;Topic vocabulary&rdquo; below to get AI-powered help.
            </p>
          </div>
        )}

        {/* Sample answer display */}
        {sampleAnswer && !loading && (
          <div className="mb-4">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Sample Answer (Band 7)</p>
            <div className="rounded-xl bg-white/[0.03] border border-white/5 p-4">
              <p className="text-sm leading-relaxed text-gray-200">{sampleAnswer.sample_answer}</p>
              {sampleAnswer.key_phrases.length > 0 && (
                <div className="mt-3 pt-3 border-t border-white/5">
                  <p className="text-xs text-gray-500 mb-2">Key phrases:</p>
                  <div className="flex flex-wrap gap-1.5">
                    {sampleAnswer.key_phrases.map((p, i) => (
                      <span key={i} className="px-2 py-0.5 rounded-full text-xs bg-teal-500/10 text-teal-400 border border-teal-500/20">
                        {p}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Topic vocabulary display */}
        {topicVocab && !loading && (
          <div className="mb-4">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Topic Vocabulary (Band 8-9)</p>
            <div className="space-y-2">
              {topicVocab.vocabulary.map((item: VocabItem, i: number) => (
                <div key={i} className="rounded-lg bg-white/[0.03] border border-white/5 p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium text-teal-300">{item.term}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-gray-500 border border-white/10">
                      {item.type.replace('_', ' ')}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 mb-1">{item.definition}</p>
                  <p className="text-xs text-gray-500 italic">&ldquo;{item.example}&rdquo;</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Bottom dock */}
      <div className="p-4 space-y-3 border-t border-white/5 shrink-0">
        {/* Suggestion chips */}
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={handleSampleAnswer}
            disabled={loading !== null}
            className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-sm text-gray-300 transition-colors disabled:opacity-50"
          >
            Sample answer
          </button>
          <button
            type="button"
            onClick={handleTopicVocab}
            disabled={loading !== null}
            className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-sm text-gray-300 transition-colors disabled:opacity-50"
          >
            Topic vocabulary
          </button>
        </div>

        {/* Pronunciation input */}
        <div className="relative flex items-center">
          <input
            type="text"
            value={pronunInput}
            onChange={(e) => setPronunInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handlePronunPractice()}
            className="w-full bg-black/20 border border-white/10 rounded-xl py-3 pl-4 pr-36 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-white/20 focus:ring-1 focus:ring-white/20 transition-all"
            placeholder="Enter word to practice pronunciation"
          />
          <button
            type="button"
            onClick={handlePronunPractice}
            disabled={pronunPlaying || !pronunInput.trim()}
            className="absolute right-1 top-1 bottom-1 glow-btn-pronun text-white text-sm font-medium px-4 rounded-lg hover:brightness-110 transition-all disabled:opacity-50"
          >
            {pronunPlaying ? 'Playing...' : 'Practice'}
          </button>
        </div>

        {/* Question navigation */}
        <div className="flex items-center justify-between pt-2">
          <button
            type="button"
            onClick={handlePrev}
            disabled={prevId === null}
            className="w-8 h-8 rounded-lg border border-white/10 flex items-center justify-center text-gray-400 hover:bg-white/5 hover:text-white transition-all disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>
          <span className="text-sm text-gray-300 line-clamp-1 flex-1 text-center px-2">
            {question?.text ?? '\u2014'}
          </span>
          <button
            type="button"
            onClick={handleNext}
            disabled={nextId === null}
            className="w-8 h-8 rounded-lg border border-white/10 flex items-center justify-center text-gray-400 hover:bg-white/5 hover:text-white transition-all disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}
