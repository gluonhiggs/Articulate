import { useEffect, useRef, useState } from 'react'
import { fetchPronunciationDetails } from '../../api/client'
import type { Attempt, PronunciationWord } from '../../types'

type Tier = 'poor' | 'unclear' | 'imprecise'

const TIER_CONFIG: Record<Tier, {
  label: string
  iconColor: string
  wordColor: string
  selectedBorder: string
  selectedBg: string
  transcriptHoverBg: string
  transcriptSelectedBg: string
  transcriptSelectedRing: string
  selectedWordTextColor: string
}> = {
  poor: {
    label: 'Poorly Pronounced',
    iconColor: 'text-red-400',
    wordColor: 'text-red-300',
    selectedBorder: 'border-red-500/30',
    selectedBg: 'bg-red-500/10',
    transcriptHoverBg: 'hover:bg-red-500/10',
    transcriptSelectedBg: 'bg-red-500/15',
    transcriptSelectedRing: 'ring-1 ring-red-500/40',
    selectedWordTextColor: 'text-red-300',
  },
  unclear: {
    label: 'Unclear',
    iconColor: 'text-orange-400',
    wordColor: 'text-orange-300',
    selectedBorder: 'border-orange-500/30',
    selectedBg: 'bg-orange-500/10',
    transcriptHoverBg: 'hover:bg-orange-500/10',
    transcriptSelectedBg: 'bg-orange-500/15',
    transcriptSelectedRing: 'ring-1 ring-orange-500/40',
    selectedWordTextColor: 'text-orange-300',
  },
  imprecise: {
    label: 'Imprecise',
    iconColor: 'text-yellow-400',
    wordColor: 'text-yellow-300',
    selectedBorder: 'border-yellow-500/30',
    selectedBg: 'bg-yellow-500/10',
    transcriptHoverBg: 'hover:bg-yellow-500/10',
    transcriptSelectedBg: 'bg-yellow-500/15',
    transcriptSelectedRing: 'ring-1 ring-yellow-500/40',
    selectedWordTextColor: 'text-yellow-300',
  },
}

const TIER_ORDER: Tier[] = ['poor', 'unclear', 'imprecise']

export function PronunciationRightPanel({
  attempt,
  onClose,
}: {
  attempt: Attempt
  onClose: () => void
}) {
  const [words, setWords] = useState<PronunciationWord[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedWord, setSelectedWord] = useState<string | null>(null)
  const [playingWord, setPlayingWord] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  useEffect(() => {
    setLoading(true)
    fetchPronunciationDetails(attempt.id)
      .then((res) => setWords(res.words))
      .catch(() => setWords(null))
      .finally(() => setLoading(false))
  }, [attempt.id])

  // Cleanup audio on unmount
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current.src = ''
        audioRef.current = null
      }
    }
  }, [])

  function playWord(word: string) {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
    setPlayingWord(word)
    const url = `/api/v1/tts/pronounce?text=${encodeURIComponent(word)}`
    // Fetch the audio first, then play - avoids browser blocking issues
    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(`TTS error: ${res.status}`)
        return res.blob()
      })
      .then((blob) => {
        const audio = new Audio(URL.createObjectURL(blob))
        audioRef.current = audio
        audio.onended = () => { setPlayingWord(null); URL.revokeObjectURL(audio.src) }
        audio.onerror = () => { setPlayingWord(null); URL.revokeObjectURL(audio.src) }
        return audio.play()
      })
      .catch((err) => {
        console.error('TTS playback failed:', err)
        setPlayingWord(null)
      })
  }

  function handleWordClick(word: string) {
    setSelectedWord(word === selectedWord ? null : word)
  }

  // Build pronunciation tier map
  const tierMap = new Map(
    words?.filter((w) => w.tier !== 'clear').map((w) => [w.word.toLowerCase(), w.tier as Tier]) ?? []
  )

  // Get the tier of the currently selected word
  const selectedTier = selectedWord ? tierMap.get(selectedWord) : undefined
  const selectedTierConfig = selectedTier ? TIER_CONFIG[selectedTier] : undefined

  // Split the transcript to render with pronunciation highlights
  const transcriptWords = attempt.transcript?.split(/(\s+)/) ?? []

  return (
    <div className="flex flex-col h-full">
      {/* Panel header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 shrink-0">
        <span className="text-sm font-medium text-teal-400">Pronunciation</span>
        <button
          onClick={onClose}
          className="w-6 h-6 rounded-full border border-white/10 flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      {/* Transcript with pronunciation highlights */}
      <div className="flex-1 overflow-y-auto p-4">
        {loading ? (
          <div className="flex items-center gap-2">
            <div className="animate-spin h-4 w-4 border-2 border-teal-400 border-t-transparent rounded-full" />
            <span className="text-gray-400 text-sm">Loading...</span>
          </div>
        ) : (
          <>
            {/* Full sentence with pronunciation highlights */}
            <div className="mb-6">
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">Full Response</p>
              <div className="text-[15px] leading-loose text-gray-200">
                {transcriptWords.map((token, i) => {
                  if (/^\s+$/.test(token)) return token
                  const clean = token.replace(/[.,!?;:'"()\-]/g, '').toLowerCase()
                  const wordTier = tierMap.get(clean)
                  const isSelected = selectedWord?.toLowerCase() === clean
                  const config = wordTier ? TIER_CONFIG[wordTier] : undefined

                  return (
                    <span
                      key={i}
                      onClick={wordTier ? () => handleWordClick(clean) : undefined}
                      className={[
                        'inline-block rounded px-0.5 py-0.5 transition-all',
                        wordTier
                          ? `pronun-word-${wordTier} ${config!.transcriptHoverBg} cursor-pointer`
                          : '',
                        isSelected ? `${config!.transcriptSelectedBg} ${config!.transcriptSelectedRing}` : '',
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
              <div className="mb-6 p-4 rounded-xl bg-white/5 border border-white/10">
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => playWord(selectedWord)}
                    className={`w-10 h-10 rounded-full flex items-center justify-center transition-colors ${
                      playingWord === selectedWord
                        ? 'bg-teal-500/30 border border-teal-500/50'
                        : 'bg-white/5 border border-white/10 hover:bg-white/10'
                    }`}
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      className={`h-4 w-4 ${playingWord === selectedWord ? 'text-teal-400 animate-pulse' : 'text-gray-300'}`}
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
                    <p className={`text-lg font-semibold ${selectedTierConfig?.selectedWordTextColor ?? 'text-gray-200'}`}>{selectedWord}</p>
                    <p className="ipa-display mt-0.5">
                      /{selectedWord}/
                    </p>
                  </div>
                </div>
              </div>
            )}

            {words && tierMap.size === 0 && (
              <div className="text-center py-8">
                <p className="text-green-400 text-sm">All words pronounced clearly</p>
              </div>
            )}
          </>
        )}
      </div>

      {/* Bottom: legend + score */}
      <div className="p-4 border-t border-white/5 shrink-0 space-y-2">
        <div className="flex items-center justify-center gap-4 text-xs">
          <span className="text-yellow-400">● Imprecise</span>
          <span className="text-orange-400">● Unclear</span>
          <span className="text-red-400">● Poor</span>
        </div>
        <p className="text-center text-sm text-gray-400 line-clamp-1">
          Pronunciation score: {attempt.pronunciation?.toFixed(1) ?? '-'}
        </p>
      </div>
    </div>
  )
}
