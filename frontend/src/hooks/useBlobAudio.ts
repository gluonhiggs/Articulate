import { useCallback, useEffect, useRef, useState } from 'react'
import { createLogger, errorData } from '../lib/log'

const log = createLogger('audio')

export function useBlobAudio(): { playing: boolean; play: (url: string) => Promise<boolean>; stop: () => void } {
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const requestRef = useRef(0)
  const [playing, setPlaying] = useState(false)

  const stop = useCallback(() => {
    requestRef.current += 1
    const audio = audioRef.current
    if (audio) {
      audio.onended = null
      audio.onerror = null
      audio.pause()
      URL.revokeObjectURL(audio.src)
      audioRef.current = null
    }
    setPlaying(false)
  }, [])

  const play = useCallback(
    (url: string): Promise<boolean> => {
      stop()
      const request = requestRef.current
      setPlaying(true)
      return fetch(url)
        .then((res) => {
          if (!res.ok) throw new Error(`Audio request failed: ${res.status}`)
          return res.blob()
        })
        .then(async (blob) => {
          if (request !== requestRef.current) return true
          const audio = new Audio(URL.createObjectURL(blob))
          audioRef.current = audio
          const finish = () => {
            if (audioRef.current === audio) stop()
          }
          audio.onended = finish
          audio.onerror = finish
          await audio.play()
          return true
        })
        .catch((err: unknown) => {
          // A request superseded by stop() or a newer play() did not fail on its own.
          if (request !== requestRef.current) return true
          // NotAllowedError is the browser's autoplay policy before a user gesture, not a bug.
          if (err instanceof Error && err.name === 'NotAllowedError') log.debug(`autoplay blocked: ${url}`)
          else log.error(`playback failed: ${url}`, errorData(err))
          stop()
          return false
        })
    },
    [stop],
  )

  useEffect(() => stop, [stop])

  return { playing, play, stop }
}
