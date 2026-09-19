import { useState } from 'react'
import { interviewAnswerAudioUrl } from '../../api/interview'
import { useBlobAudio } from '../../hooks/useBlobAudio'

export function AnswerAudioButton({ answerId }: { answerId: number }) {
  const { playing, play, stop } = useBlobAudio()
  const [unavailable, setUnavailable] = useState(false)

  function handleClick() {
    if (playing) {
      stop()
      return
    }
    void play(interviewAnswerAudioUrl(answerId)).then((ok) => setUnavailable(!ok))
  }

  return (
    <button
      onClick={handleClick}
      disabled={unavailable}
      title={unavailable ? 'Recording is not available' : undefined}
      className="flex items-center gap-2 px-4 py-2 rounded-lg border border-teal-500/40 bg-teal-500/10 text-teal-400 text-sm hover:bg-teal-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {playing ? (
        <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" viewBox="0 0 24 24" fill="currentColor">
          <rect x="6" y="4" width="4" height="16" />
          <rect x="14" y="4" width="4" height="16" />
        </svg>
      ) : (
        <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" viewBox="0 0 24 24" fill="currentColor">
          <polygon points="5 3 19 12 5 21 5 3" />
        </svg>
      )}
      {unavailable ? 'Audio unavailable' : playing ? 'Stop' : 'Play my answer'}
    </button>
  )
}
