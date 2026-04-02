import { useEffect, useRef, useState } from 'react'
import { getAttemptAudioUrl } from '../../api/client'
import type { Attempt } from '../../types'
import { ImproveSection } from './ImproveSection'
import { InlineCorrectedText } from './InlineCorrectedText'
import { ScoreCircle } from './ScoreCircle'
import { ScoreTags } from './ScoreTags'

export function ActiveAttemptCard({
  attempt,
  index,
  isNew,
  shownPronunIds,
  onShowPronunciation,
}: {
  attempt: Attempt
  index: number
  isNew: boolean
  shownPronunIds: Set<number>
  onShowPronunciation: (attempt: Attempt) => void
}) {
  const [expanded, setExpanded] = useState(true)
  const [playing, setPlaying] = useState(false)
  const [audioAvailable, setAudioAvailable] = useState<boolean | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const objectUrlRef = useRef<string | null>(null)

  // Check audio availability and stop on unmount
  useEffect(() => {
    // Show button if audio_path is set; hide on play error (handled in handlePlayPause)
    setAudioAvailable(!!attempt.audio_path)

    return () => {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current.src = ''
        audioRef.current = null
      }
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current)
        objectUrlRef.current = null
      }
    }
  }, [attempt.id, attempt.audio_path])

  function handlePlayPause() {
    if (playing) {
      // Pause
      if (audioRef.current) {
        audioRef.current.pause()
      }
      setPlaying(false)
      return
    }

    // Play
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }

    const url = getAttemptAudioUrl(attempt.id)
    fetch(url)
      .then((res) => {
        if (!res.ok) {
          setAudioAvailable(false)
          return
        }
        return res.blob()
      })
      .then((blob) => {
        if (!blob) return
        const objectUrl = URL.createObjectURL(blob)
        objectUrlRef.current = objectUrl
        const audio = new Audio(objectUrl)
        audioRef.current = audio
        setPlaying(true)
        audio.onended = () => {
          setPlaying(false)
          URL.revokeObjectURL(objectUrl)
          objectUrlRef.current = null
        }
        audio.onerror = () => {
          setPlaying(false)
          URL.revokeObjectURL(objectUrl)
          objectUrlRef.current = null
        }
        return audio.play()
      })
      .catch(() => setPlaying(false))
  }

  if (attempt.status === 'processing') {
    return (
      <div className={`rounded-xl p-5 glow-border-active bg-card ${isNew ? 'slide-in-top' : ''}`}>
        <div className="flex items-center gap-3">
          <span className="text-gray-500 text-xs font-mono">#{index + 1}</span>
          <div className="animate-spin h-4 w-4 border-2 border-teal-400 border-t-transparent rounded-full" />
          <span className="text-gray-400 text-sm">Scoring...</span>
        </div>
      </div>
    )
  }

  if (attempt.status === 'failed') {
    return (
      <div className={`rounded-xl p-5 bg-card border border-red-500/30 ${isNew ? 'slide-in-top' : ''}`}>
        <span className="text-gray-500 text-xs font-mono">#{index + 1}</span>
        <p className="text-red-400 text-sm mt-1">Processing failed — please try recording again.</p>
      </div>
    )
  }

  return (
    <div className={`rounded-xl p-5 glow-border-active bg-card relative ${isNew ? 'slide-in-top' : ''}`}>
      <div className="flex gap-4">
        {/* Play button — only shown when audio is available */}
        {attempt.audio_path && audioAvailable !== false && (
          <button
            onClick={handlePlayPause}
            className="w-8 h-8 shrink-0 rounded-full bg-teal-500/20 flex items-center justify-center border border-teal-500/50 hover:bg-teal-500/30 transition-colors"
          >
            {playing ? (
              /* Pause icon */
              <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 text-teal-400" viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="4" width="4" height="16" />
                <rect x="14" y="4" width="4" height="16" />
              </svg>
            ) : (
              /* Play icon */
              <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 text-teal-400 ml-0.5" viewBox="0 0 24 24" fill="currentColor">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
            )}
          </button>
        )}

        {/* Transcript with inline corrections */}
        <div className="flex-1 text-[15px] leading-relaxed text-gray-200">
          {attempt.transcript ? (
            <InlineCorrectedText
              transcript={attempt.transcript}
              highlights={attempt.error_highlights}
            />
          ) : (
            <span className="text-gray-500 italic">No transcript</span>
          )}
        </div>

        {/* Score circle */}
        <div className="shrink-0 flex flex-col items-center gap-1">
          <ScoreCircle score={attempt.score} size="lg" />
        </div>
      </div>

      {/* Score tags */}
      <div className="mt-4 ml-12">
        <ScoreTags
          attempt={attempt}
          pronunDetailsShown={shownPronunIds.has(attempt.id)}
          onPronunDetails={() => onShowPronunciation(attempt)}
        />
      </div>

      {expanded && (
        <>
          {/* Feedback */}
          {attempt.feedback_text && (
            <div className="mt-4 ml-12 bg-background/50 rounded-lg p-3">
              <p className="text-gray-400 text-sm leading-relaxed">{attempt.feedback_text}</p>
            </div>
          )}

          {/* Improve section */}
          <div className="ml-12">
            <ImproveSection attemptId={attempt.id} />
          </div>
        </>
      )}

      {/* Collapse toggle */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="absolute -bottom-3 left-1/2 -translate-x-1/2 w-6 h-6 rounded-full bg-card border border-cardBorder flex items-center justify-center cursor-pointer hover:bg-white/5 z-10"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className={`h-2.5 w-2.5 text-gray-400 transition-transform ${expanded ? '' : 'rotate-180'}`}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={3}
        >
          <polyline points="18 15 12 9 6 15" />
        </svg>
      </button>
    </div>
  )
}
