import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { RecordingBar } from '../components/recording/RecordingBar'
import type { RecordingStatus } from '../store/recordingStore'

const TRANSCRIPT = 'I usually wake up somewhere between four and six in the morning.'

function render(status: RecordingStatus, transcript: string | null) {
  return renderToStaticMarkup(
    <RecordingBar
      status={status}
      elapsed={0}
      max={60}
      onStart={() => {}}
      onStop={() => {}}
      backendStatus={status === 'polling' ? 'scoring' : null}
      transcript={transcript}
    />,
  )
}

describe('RecordingBar transcript preview', () => {
  it('shows the transcript while the answer is being scored', () => {
    const html = render('polling', TRANSCRIPT)
    expect(html).toContain(TRANSCRIPT)
    expect(html).toContain('What you said')
  })

  it('shows nothing when the transcript has not been saved yet', () => {
    expect(render('polling', null)).not.toContain('What you said')
    expect(render('polling', '')).not.toContain('What you said')
  })

  it('leaves the recording controls untouched', () => {
    expect(render('idle', null)).toContain('Record')
    expect(render('recording', TRANSCRIPT)).not.toContain(TRANSCRIPT)
    expect(render('recording', TRANSCRIPT)).toContain('Recording')
  })
})
