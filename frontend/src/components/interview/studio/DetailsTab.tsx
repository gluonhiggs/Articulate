import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { updateInterviewPack } from '../../../api/interview'
import type { InterviewLevel, InterviewPackDetail, InterviewPackInput, InterviewRole } from '../../../types/interview'
import { apiErrorDetail } from '../utils'
import { LEVEL_OPTIONS, ROLE_OPTIONS, isPackInputDirty, packToInput, toPackPayload } from './studioModel'
import {
  Field,
  Notice,
  Spinner,
  cardClass,
  inputClass,
  primaryButtonClass,
  secondaryButtonClass,
} from './studioUi'

interface DetailsTabProps {
  pack: InterviewPackDetail
  onDirtyChange: (dirty: boolean) => void
}

export function DetailsTab({ pack, onDirtyChange }: DetailsTabProps) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<InterviewPackInput | null>(null)
  const current = form ?? packToInput(pack)
  const dirty = isPackInputDirty(form, pack)

  useEffect(() => onDirtyChange(dirty), [dirty, onDirtyChange])

  const saveMutation = useMutation({
    mutationFn: (input: InterviewPackInput) => updateInterviewPack(pack.id, toPackPayload(input)),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['interview'] })
      setForm(null)
    },
  })

  function update<K extends keyof InterviewPackInput>(field: K, value: InterviewPackInput[K]) {
    setForm({ ...current, [field]: value })
  }

  const titleMissing = !current.title.trim()

  return (
    <div className={cardClass}>
      <fieldset disabled={saveMutation.isPending} className="space-y-4 min-w-0">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Title">
            <input
              type="text"
              maxLength={200}
              value={current.title}
              onChange={(e) => update('title', e.target.value)}
              className={inputClass}
            />
          </Field>
          <Field label="Author">
            <input
              type="text"
              maxLength={100}
              value={current.author}
              onChange={(e) => update('author', e.target.value)}
              placeholder="Coach name"
              className={inputClass}
            />
          </Field>
          <Field label="Role">
            <select
              value={current.role}
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
              value={current.level}
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
        </div>

        <Field
          label="Job description"
          hint={`${current.job_description.length.toLocaleString()} / 20,000 characters. Draft with AI uses it to ask what this client would ask.`}
        >
          <textarea
            rows={10}
            maxLength={20_000}
            value={current.job_description}
            onChange={(e) => update('job_description', e.target.value)}
            placeholder="Paste the client's job description"
            className={inputClass}
          />
        </Field>

        {titleMissing && <Notice tone="error">Title is required.</Notice>}
        {saveMutation.isError && <Notice tone="error">Could not save: {apiErrorDetail(saveMutation.error)}</Notice>}

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className={primaryButtonClass}
            disabled={!dirty || titleMissing}
            onClick={() => saveMutation.mutate(current)}
          >
            {saveMutation.isPending && <Spinner />}
            Save details
          </button>
          {dirty && (
            <button type="button" className={secondaryButtonClass} onClick={() => setForm(null)}>
              Discard changes
            </button>
          )}
          <span className="ml-auto text-xs text-textSecondary">Questionnaire version v{pack.version}</span>
        </div>
      </fieldset>
    </div>
  )
}
