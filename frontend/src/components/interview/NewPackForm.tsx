import { useState } from 'react'
import type { InterviewLevel, InterviewPackInput, InterviewRole } from '../../types/interview'
import { LEVEL_OPTIONS, ROLE_OPTIONS, toPackPayload } from './studio/studioModel'
import { Field, inputClass } from './studio/studioUi'
import { outlineButtonClass } from './ui'

export function NewPackForm({
  submitting,
  error,
  onSubmit,
  onCancel,
}: {
  submitting: boolean
  error: string | null
  onSubmit: (input: InterviewPackInput) => void
  onCancel: () => void
}) {
  const [input, setInput] = useState<InterviewPackInput>({
    title: '',
    role: 'swe',
    level: 'mid',
    author: '',
    job_description: '',
  })

  function update<K extends keyof InterviewPackInput>(key: K, value: InterviewPackInput[K]) {
    setInput((prev) => ({ ...prev, [key]: value }))
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!input.title.trim()) return
    onSubmit(toPackPayload(input))
  }

  return (
    <form onSubmit={handleSubmit} className="bg-card border border-cardBorder rounded-xl p-5 space-y-4">
      <div>
        <p className="text-textPrimary font-semibold text-sm">New interview pack</p>
        <p className="text-textSecondary text-xs mt-1">
          You can add sources, questions and the approved answer key in Pack Studio next.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field label="Title" className="md:col-span-2">
          <input
            value={input.title}
            onChange={(e) => update('title', e.target.value)}
            placeholder="e.g. Data Engineer - retail client"
            maxLength={200}
            required
            className={inputClass}
          />
        </Field>

        <Field label="Role">
          <select
            value={input.role}
            onChange={(e) => update('role', e.target.value as InterviewRole)}
            className={inputClass}
          >
            {ROLE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Level">
          <select
            value={input.level}
            onChange={(e) => update('level', e.target.value as InterviewLevel)}
            className={inputClass}
          >
            {LEVEL_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Author" className="md:col-span-2">
          <input
            value={input.author}
            onChange={(e) => update('author', e.target.value)}
            placeholder="Who prepares this pack"
            maxLength={100}
            className={inputClass}
          />
        </Field>

        <Field label="Job description" className="md:col-span-2">
          <textarea
            value={input.job_description}
            onChange={(e) => update('job_description', e.target.value)}
            placeholder="Paste the client's job description (optional)"
            rows={5}
            maxLength={20_000}
            className={`resize-y ${inputClass}`}
          />
        </Field>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      <div className="flex items-center justify-end gap-2">
        <button type="button" onClick={onCancel} className={outlineButtonClass}>
          Cancel
        </button>
        <button
          type="submit"
          disabled={submitting || !input.title.trim()}
          className="px-5 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-purple-600 text-white font-semibold text-sm hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? 'Creating...' : 'Create and open studio'}
        </button>
      </div>
    </form>
  )
}
