/**
 * Saving a different CV retires the introductions written from the old one, so the
 * notice has to say so: a question disappearing from About you without a word reads
 * as a bug.
 */

import { describe, expect, it } from 'vitest'
import { savedMessage } from '../pages/interview/CandidateCv'
import type { CandidateProfileSaved } from '../types/interview'

function saved(overrides: Partial<CandidateProfileSaved>): CandidateProfileSaved {
  return {
    full_name: 'Duong H. D. Tran',
    target_role: '',
    cv_text: 'cv',
    cv_filename: 'cv.pdf',
    has_cv: true,
    introductions_retired: 0,
    introduction_written: false,
    ...overrides,
  }
}

describe('savedMessage', () => {
  it('says only Saved when the CV text did not change', () => {
    expect(savedMessage(saved({}))).toBe('Saved.')
  })

  it('reports the old introductions retired and the new one written', () => {
    expect(savedMessage(saved({ introductions_retired: 3, introduction_written: true }))).toBe(
      'Saved. 3 introduction questions from the old CV retired. A new one was written from this CV.',
    )
  })

  it('tells the reader to write one later when the quota stopped it', () => {
    expect(savedMessage(saved({ introductions_retired: 1, introduction_written: false }))).toBe(
      'Saved. 1 introduction question from the old CV retired. Write a new one on the CV tab when the quota allows.',
    )
  })

  it('reports a first introduction written for a first CV', () => {
    expect(savedMessage(saved({ introduction_written: true }))).toBe(
      'Saved. An introduction question was written from this CV.',
    )
  })
})
