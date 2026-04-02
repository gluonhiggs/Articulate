import { useEffect, useRef, useState } from 'react'
import type { PronunciationFeedItem } from './feedTypes'

function LoadingRow({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-2 py-3">
      <div className="animate-spin h-4 w-4 border-2 border-teal-400 border-t-transparent rounded-full shrink-0" />
      <span className="text-gray-400 text-sm">{text}</span>
    </div>
  )
}

export function PronunciationCard({
  item,
  onDismiss,
}: {
  item: PronunciationFeedItem
  onDismiss: () => void
}) {
  const [selectedWord, setSelectedWord] = useState<string | null>(null)
  const [playingWord, setPlayingWord] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current = null
      }
    }
  }, [])

  function playWord(word: string) {
    if (audioRef.current) { audioRef.current.pause(); audioRef.current = null }
    setPlayingWord(word)
    fetch(`/api/v1/tts/pronounce?text=${encodeURIComponent(word)}`)
      .then((res) => { if (!res.ok) throw new Error(); return res.blob() })
      .then((blob) => {
        const audio = new Audio(URL.createObjectURL(blob))
        audioRef.current = audio
        audio.onended = () => { setPlayingWord(null); URL.revokeObjectURL(audio.src) }
        audio.onerror = () => { setPlayingWord(null); URL.revokeObjectURL(audio.src) }
        return audio.play()
      })
      .catch(() => setPlayingWord(null))
  }

  function handleWordClick(word: string) {
    setSelectedWord((w) => (w === word ? null : word))
  }

  const flaggedSet = new Set(
    item.words?.filter((w) => w.is_flagged).map((w) => w.word.toLowerCase()) ?? []
  )
  const transcriptTokens = item.transcript?.split(/(\s+)/) ?? []

  return (
    <div className="mb-4 rounded-xl bg-white/[0.03] border border-white/5 overflow-hidden">
      {/* Card header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/5">
        <span className="text-xs text-gray-500 uppercase tracking-wider">Pronunciation Analysis</span>
        <button
          onClick={onDismiss}
          className="w-5 h-5 rounded-full border border-white/10 flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
          aria-label="Dismiss"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-2.5 w-2.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      {/* Card body */}
      <div className="p-4">
        {item.loading ? (
          <LoadingRow text="Loading pronunciation details..." />
        ) : item.error ? (
          <div className="rounded-lg bg-red-500/10 border border-red-500/20 p-3">
            <p className="text-red-400 text-sm">{item.error}</p>
          </div>
        ) : (
          <>
            {/* Full transcript with highlights */}
            <div className="mb-4">
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Full Response</p>
              <div className="text-[15px] leading-loose text-gray-200">
                {transcriptTokens.map((token, i) => {
                  if (/^\s+$/.test(token)) return token
                  const clean = token.replace(/[.,!?;:'"()\-]/g, '').toLowerCase()
                  const isFlagged = flaggedSet.has(clean)
                  const isSelected = selectedWord === clean
                  return (
                    <span
                      key={i}
                      onClick={isFlagged ? () => handleWordClick(clean) : undefined}
                      className={[
                        'inline-block rounded px-0.5 py-0.5 transition-all',
                        isFlagged ? 'pronun-word-flagged hover:bg-orange-500/10 cursor-pointer' : '',
                        isSelected ? 'bg-orange-500/15 ring-1 ring-orange-500/40' : '',
                      ].join(' ')}
                    >
                      {token}
                    </span>
                  )
                })}
              </div>
            </div>

            {/* Selected word IPA + audio */}
            {selectedWord && (
              <div className="mb-4 p-3 rounded-xl bg-white/5 border border-white/10">
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => playWord(selectedWord)}
                    className={`w-9 h-9 rounded-full flex items-center justify-center transition-colors ${
                      playingWord === selectedWord
                        ? 'bg-teal-500/30 border border-teal-500/50'
                        : 'bg-white/5 border border-white/10 hover:bg-white/10'
                    }`}
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      className={`h-3.5 w-3.5 ${playingWord === selectedWord ? 'text-teal-400 animate-pulse' : 'text-gray-300'}`}
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                      <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
                    </svg>
                  </button>
                  <div>
                    <p className="text-base font-semibold text-orange-300">{selectedWord}</p>
                    <p className="ipa-display mt-0.5">/{selectedWord}/</p>
                  </div>
                </div>
              </div>
            )}

            {/* Flagged words list */}
            {item.words && item.words.filter((w) => w.is_flagged).length > 0 && (
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">
                  Flagged Words ({item.words.filter((w) => w.is_flagged).length})
                </p>
                <div className="space-y-1.5">
                  {item.words
                    .filter((w) => w.is_flagged)
                    .map((w, i) => (
                      <button
                        key={i}
                        onClick={() => { handleWordClick(w.word.toLowerCase()); playWord(w.word) }}
                        className={`flex items-center gap-3 w-full px-3 py-2 rounded-lg text-left transition-all ${
                          selectedWord === w.word.toLowerCase()
                            ? 'bg-orange-500/10 border border-orange-500/30'
                            : 'bg-white/[0.03] border border-white/5 hover:bg-white/[0.06]'
                        }`}
                      >
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          className={`h-3.5 w-3.5 flex-shrink-0 ${playingWord === w.word ? 'text-teal-400 animate-pulse' : 'text-orange-400'}`}
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth={2}
                        >
                          <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                          <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
                        </svg>
                        <span className="text-orange-300 font-medium text-sm">{w.word}</span>
                        <span className="text-gray-500 text-xs ml-auto">
                          {Math.round(w.confidence * 100)}%
                        </span>
                      </button>
                    ))}
                </div>
              </div>
            )}

            {item.words && item.words.filter((w) => w.is_flagged).length === 0 && (
              <p className="text-green-400 text-sm text-center py-2">All words pronounced clearly</p>
            )}

            {/* Pronunciation score */}
            <div className="mt-3 pt-3 border-t border-white/5">
              <p className="text-center text-xs text-gray-500">
                Pronunciation score: {item.pronunciationScore?.toFixed(1) ?? '—'}
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
