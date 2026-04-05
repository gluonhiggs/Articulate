import { useCallback, useRef, useState } from 'react'

interface UseRecorderReturn {
  isRecording: boolean
  startRecording: () => Promise<void>
  stopRecording: () => void
  audioBlob: Blob | null
  resetAudioBlob: () => void
}

export function useRecorder(maxSeconds: number): UseRecorderReturn {
  const [isRecording, setIsRecording] = useState(false)
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<BlobPart[]>([])
  const autoStopTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const streamRef = useRef<MediaStream | null>(null)

  const stopRecording = useCallback(() => {
    if (autoStopTimerRef.current) {
      clearTimeout(autoStopTimerRef.current)
      autoStopTimerRef.current = null
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    }
  }, [])

  const startRecording = useCallback(async () => {
    // Reset previous state
    chunksRef.current = []
    setAudioBlob(null)

    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error(
        'Microphone is not available. Open the app at http://localhost:5173 and ensure your browser allows microphone access.'
      )
    }

    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
        },
      })
    } catch (err) {
      throw new Error(`Microphone access denied - check browser permissions and try again. (${String(err)})`)
    }

    streamRef.current = stream

    // Prefer opus/webm; fall back to mp4 for iOS Safari
    const preferredTypes = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']
    const mimeType = preferredTypes.find((t) => MediaRecorder.isTypeSupported(t)) ?? ''
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : {})
    mediaRecorderRef.current = recorder

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        chunksRef.current.push(event.data)
      }
    }

    recorder.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: mimeType })
      setAudioBlob(blob)
      setIsRecording(false)

      // Stop all tracks to release microphone
      stream.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }

    recorder.start(100) // collect data every 100ms
    setIsRecording(true)

    // Auto-stop after maxSeconds
    autoStopTimerRef.current = setTimeout(() => {
      if (recorder.state !== 'inactive') {
        recorder.stop()
      }
    }, maxSeconds * 1000)
  }, [maxSeconds])

  const resetAudioBlob = useCallback(() => setAudioBlob(null), [])

  return { isRecording, startRecording, stopRecording, audioBlob, resetAudioBlob }
}
