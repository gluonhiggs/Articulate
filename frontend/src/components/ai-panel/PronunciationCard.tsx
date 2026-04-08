import { useEffect, useRef, useState } from 'react'
import type { PronunciationFeedItem } from './feedTypes'
import type { PronunciationWord } from '../../types'

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

  const tierMap = new Map(
    item.words?.filter((w) => w.tier !== 'clear').map((w) => [w.word.toLowerCase(), w.tier as Tier]) ?? []
  )

  const selectedTier = selectedWord ? tierMap.get(selectedWord) : undefined
  const selectedTierConfig = selectedTier ? TIER_CONFIG[selectedTier] : undefined

  // Group words by tier
  const wordsByTier = new Map<Tier, PronunciationWord[]>()
  for (const tier of TIER_ORDER) {
    const tierWords = item.words?.filter((w) => w.tier === tier) ?? []
    if (tierWords.length > 0) {
      wordsByTier.set(tier, tierWords)
    }
  }

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
                  const wordTier = tierMap.get(clean)
                  const isSelected = selectedWord === clean
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
                    <p className={`text-base font-semibold ${selectedTierConfig?.selectedWordTextColor ?? 'text-gray-200'}`}>{selectedWord}</p>
                    <p className="ipa-display mt-0.5">/{selectedWord}/</p>
                  </div>
                </div>
              </div>
            )}

            {/* Tiered word lists */}
            {TIER_ORDER.map((tier) => {
              const tierWords = wordsByTier.get(tier)
              if (!tierWords) return null
              const config = TIER_CONFIG[tier]
              return (
                <div key={tier} className="mb-3">
                  <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">
                    {config.label} ({tierWords.length})
                  </p>
                  <div className="space-y-1.5">
                    {tierWords.map((w, i) => (
                      <button
                        key={i}
                        onClick={() => { handleWordClick(w.word.toLowerCase()); playWord(w.word) }}
                        className={`flex items-center gap-3 w-full px-3 py-2 rounded-lg text-left transition-all ${
                          selectedWord === w.word.toLowerCase()
                            ? `${config.selectedBg} border ${config.selectedBorder}`
                            : 'bg-white/[0.03] border border-white/5 hover:bg-white/[0.06]'
                        }`}
                      >
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          className={`h-3.5 w-3.5 flex-shrink-0 ${playingWord === w.word ? 'text-teal-400 animate-pulse' : config.iconColor}`}
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth={2}
                        >
                          <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                          <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
                        </svg>
                        <span className={`${config.wordColor} font-medium text-sm`}>{w.word}</span>
                        <span className="text-gray-500 text-xs ml-auto">
                          {Math.round(w.confidence * 100)}%
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )
            })}

            {item.words && tierMap.size === 0 && (
              <p className="text-green-400 text-sm text-center py-2">All words pronounced clearly</p>
            )}

            {/* Pronunciation score */}
            <div className="mt-3 pt-3 border-t border-white/5">
              <p className="text-center text-xs text-gray-500">
                Pronunciation score: {item.pronunciationScore?.toFixed(1) ?? '-'}
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
