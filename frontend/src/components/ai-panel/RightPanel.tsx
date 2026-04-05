import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchPronunciationDetails, fetchSampleAnswer, fetchTopicVocab } from '../../api/client'
import type { Attempt, Question } from '../../types'
import { partRoute } from '../questions/utils'
import type { FeedItem, PronunciationFeedItem, SampleAnswerFeedItem, TopicVocabFeedItem } from './feedTypes'
import { PronunciationCard } from './PronunciationCard'
import { SampleAnswerCard } from './SampleAnswerCard'
import { TopicVocabCard } from './TopicVocabCard'

export function RightPanel({
  question,
  pronunAttempt,
  allQuestions,
}: {
  question: Question | null
  pronunAttempt: Attempt | null
  allQuestions: Question[]
}) {
  const navigate = useNavigate()
  const [feedItems, setFeedItems] = useState<FeedItem[]>([])
  const [pronunInput, setPronunInput] = useState('')
  const [pronunPlaying, setPronunPlaying] = useState(false)
  const pronunAudioRef = useRef<HTMLAudioElement | null>(null)
  const feedBottomRef = useRef<HTMLDivElement>(null)
  // Tracks which attempt IDs have already been appended to the feed
  const addedPronunIdsRef = useRef<Set<number>>(new Set())
  // Tracks vocab terms already shown this session - passed to backend to avoid repetition
  const shownVocabTermsRef = useRef<string[]>([])

  // Navigation
  const currentIndex = question ? allQuestions.findIndex((q) => q.id === question.id) : -1
  const prevId = currentIndex > 0 ? allQuestions[currentIndex - 1].id : null
  const nextId =
    currentIndex < allQuestions.length - 1 && currentIndex >= 0
      ? allQuestions[currentIndex + 1].id
      : null

  // Clear feed when question changes
  useEffect(() => {
    setFeedItems([])
    addedPronunIdsRef.current = new Set()
    shownVocabTermsRef.current = []
    setPronunInput('')
  }, [question?.id])

  // React to a new pronunAttempt - append a pronunciation card
  useEffect(() => {
    if (!pronunAttempt) return
    if (addedPronunIdsRef.current.has(pronunAttempt.id)) return
    addedPronunIdsRef.current.add(pronunAttempt.id)

    const newItem: PronunciationFeedItem = {
      id: crypto.randomUUID(),
      kind: 'pronunciation',
      attemptId: pronunAttempt.id,
      transcript: pronunAttempt.transcript,
      pronunciationScore: pronunAttempt.pronunciation,
      words: null,
      loading: true,
      error: null,
    }

    setFeedItems((prev) => [...prev, newItem])

    fetchPronunciationDetails(pronunAttempt.id)
      .then((res) => {
        setFeedItems((prev) =>
          prev.map((item) =>
            item.id === newItem.id
              ? ({ ...item, words: res.words, loading: false } as PronunciationFeedItem)
              : item,
          ),
        )
      })
      .catch((err: unknown) => {
        setFeedItems((prev) =>
          prev.map((item) =>
            item.id === newItem.id
              ? ({
                  ...item,
                  loading: false,
                  error: err instanceof Error ? err.message : 'Failed to load pronunciation details',
                } as PronunciationFeedItem)
              : item,
          ),
        )
      })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pronunAttempt])

  // Scroll to bottom when a new card is appended
  useEffect(() => {
    feedBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [feedItems.length])

  function dismissItem(itemId: string) {
    setFeedItems((prev) => prev.filter((item) => item.id !== itemId))
  }

  function handleSampleAnswer() {
    if (!question) return
    const newItem: SampleAnswerFeedItem = {
      id: crypto.randomUUID(),
      kind: 'sample_answer',
      data: null,
      loading: true,
      error: null,
    }
    setFeedItems((prev) => [...prev, newItem])
    fetchSampleAnswer(question.id)
      .then((res) => {
        setFeedItems((prev) =>
          prev.map((item) =>
            item.id === newItem.id
              ? ({ ...item, data: res, loading: false } as SampleAnswerFeedItem)
              : item,
          ),
        )
      })
      .catch((err: unknown) => {
        setFeedItems((prev) =>
          prev.map((item) =>
            item.id === newItem.id
              ? ({
                  ...item,
                  loading: false,
                  error: err instanceof Error ? err.message : 'Failed to generate sample answer',
                } as SampleAnswerFeedItem)
              : item,
          ),
        )
      })
  }

  function handleTopicVocab() {
    if (!question) return
    const newItem: TopicVocabFeedItem = {
      id: crypto.randomUUID(),
      kind: 'topic_vocab',
      vocabData: null,
      loading: true,
      error: null,
    }
    setFeedItems((prev) => [...prev, newItem])
    fetchTopicVocab(question.id, shownVocabTermsRef.current)
      .then((res) => {
        // Accumulate shown terms so next click excludes them
        const newTerms = res.vocabulary.map((v) => v.term)
        shownVocabTermsRef.current = [...shownVocabTermsRef.current, ...newTerms]
        setFeedItems((prev) =>
          prev.map((item) =>
            item.id === newItem.id
              ? ({ ...item, vocabData: res, loading: false } as TopicVocabFeedItem)
              : item,
          ),
        )
      })
      .catch((err: unknown) => {
        setFeedItems((prev) =>
          prev.map((item) =>
            item.id === newItem.id
              ? ({
                  ...item,
                  loading: false,
                  error: err instanceof Error ? err.message : 'Failed to generate vocabulary',
                } as TopicVocabFeedItem)
              : item,
          ),
        )
      })
  }

  function handlePronunPractice() {
    const word = pronunInput.trim()
    if (!word) return
    if (pronunAudioRef.current) { pronunAudioRef.current.pause(); pronunAudioRef.current = null }
    setPronunPlaying(true)
    fetch(`/api/v1/tts/pronounce?text=${encodeURIComponent(word)}`)
      .then((res) => { if (!res.ok) throw new Error(`TTS error: ${res.status}`); return res.blob() })
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

  return (
    <div className="right-panel flex flex-col h-full">
      {/* Tab bar */}
      <div className="flex border-b border-white/10 px-4 pt-2 shrink-0">
        <div className="flex-1 pb-3 text-sm font-medium text-teal-400 border-b-2 border-teal-400 text-center">
          AI Support
        </div>
      </div>

      {/* Feed scroll area */}
      <div className="flex-1 overflow-y-auto p-4">
        {feedItems.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-gray-600 text-sm italic text-center">
              Click &ldquo;Sample answer&rdquo; or &ldquo;Topic vocabulary&rdquo; below to get AI-powered help.
            </p>
          </div>
        ) : (
          feedItems.map((item) => {
            if (item.kind === 'pronunciation') {
              return (
                <PronunciationCard
                  key={item.id}
                  item={item}
                  onDismiss={() => dismissItem(item.id)}
                />
              )
            }
            if (item.kind === 'sample_answer') {
              return (
                <SampleAnswerCard
                  key={item.id}
                  item={item}
                  onDismiss={() => dismissItem(item.id)}
                />
              )
            }
            if (item.kind === 'topic_vocab') {
              return (
                <TopicVocabCard
                  key={item.id}
                  item={item}
                  onDismiss={() => dismissItem(item.id)}
                />
              )
            }
            return null
          })
        )}
        {/* Scroll anchor */}
        <div ref={feedBottomRef} />
      </div>

      {/* Bottom dock */}
      <div className="p-4 space-y-3 border-t border-white/5 shrink-0">
        {/* Action chips */}
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={handleSampleAnswer}
            disabled={!question}
            className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-sm text-gray-300 transition-colors disabled:opacity-50"
          >
            Sample answer
          </button>
          <button
            type="button"
            onClick={handleTopicVocab}
            disabled={!question}
            className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-sm text-gray-300 transition-colors disabled:opacity-50"
          >
            Topic vocabulary
          </button>
        </div>

        {/* Pronunciation practice input */}
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
