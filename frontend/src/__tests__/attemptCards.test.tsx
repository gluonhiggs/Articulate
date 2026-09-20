import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { ActiveAttemptCard } from '../components/questions/ActiveAttemptCard'
import { PrevAttemptCard } from '../components/questions/PrevAttemptCard'
import type { Attempt } from '../types'

const TRANSCRIPT = 'I usually roll out of bed anywhere between four and six a.m.'

function attempt(status: Attempt['status'], transcript: string | null = TRANSCRIPT): Attempt {
  return {
    id: 4,
    question_id: 1,
    audio_path: 'data/audio/4.webm',
    transcript,
    score: null,
    fluency: null,
    vocabulary: null,
    grammar: null,
    pronunciation: null,
    feedback_text: null,
    usage_errors: null,
    duration_seconds: 44.7,
    status,
    created_at: '2026-09-19T12:16:04',
  }
}

function prev(status: Attempt['status'], transcript: string | null = TRANSCRIPT) {
  return renderToStaticMarkup(
    <PrevAttemptCard attempt={attempt(status, transcript)} index={3} isNew={false} onSelect={() => {}} />,
  )
}

function active(status: Attempt['status'], transcript: string | null = TRANSCRIPT) {
  return renderToStaticMarkup(
    <ActiveAttemptCard
      attempt={attempt(status, transcript)}
      index={3}
      isNew={false}
      shownPronunIds={new Set()}
      onShowPronunciation={() => {}}
    />,
  )
}

describe('attempt cards', () => {
  it.each([
    ['processing', 'Processing...'],
    ['transcribing', 'Transcribing...'],
    ['scoring', 'Scoring...'],
  ] as const)('shows progress for %s', (status, label) => {
    expect(prev(status, null)).toContain(label)
    expect(prev(status, null)).not.toContain('No transcript')
    expect(active(status, null)).toContain(label)
    expect(active(status, null)).not.toContain('No transcript')
  })

  it('shows the saved transcript and the reason when scoring hit the daily quota', () => {
    const html = active('failed:quota')
    expect(html).toContain('quota')
    expect(html).toContain(TRANSCRIPT)
    expect(html).not.toContain('No transcript')
  })

  it.each(['failed', 'failed:transcription', 'failed:empty_audio', 'failed:scoring'] as const)(
    'renders %s as a failure, not as an unscored answer',
    (status) => {
      expect(prev(status, null)).not.toContain('No transcript')
      expect(active(status, null)).not.toContain('No transcript')
    },
  )

  it('still renders a ready attempt normally', () => {
    expect(active('ready')).toContain(TRANSCRIPT)
    expect(prev('ready')).toContain(TRANSCRIPT)
  })
})
