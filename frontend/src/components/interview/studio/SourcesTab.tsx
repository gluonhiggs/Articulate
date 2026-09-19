import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { addInterviewSource, deleteInterviewSource } from '../../../api/interview'
import type { InterviewPackDetail, InterviewSourceInput } from '../../../types/interview'
import { apiErrorDetail } from '../utils'
import { MAX_SOURCE_CHARS, plural } from './studioModel'
import {
  Field,
  Notice,
  PlusIcon,
  Spinner,
  cardClass,
  dangerButtonClass,
  inputClass,
  primaryButtonClass,
} from './studioUi'

interface SourcesTabProps {
  pack: InterviewPackDetail
  onDirtyChange: (dirty: boolean) => void
}

const EMPTY_FORM = { title: '', url: '', content: '' }

export function SourcesTab({ pack, onDirtyChange }: SourcesTabProps) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState(EMPTY_FORM)
  const dirty = Object.values(form).some((value) => value.trim() !== '')

  useEffect(() => onDirtyChange(dirty), [dirty, onDirtyChange])

  const addMutation = useMutation({
    mutationFn: (input: InterviewSourceInput) => addInterviewSource(pack.id, input),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['interview'] })
      setForm(EMPTY_FORM)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (sourceId: number) => deleteInterviewSource(pack.id, sourceId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['interview'] }),
  })

  function handleAdd() {
    addMutation.mutate({ title: form.title.trim(), url: form.url.trim() || null, content: form.content.trim() })
  }

  function handleDelete(sourceId: number, title: string) {
    if (window.confirm(`Delete source "${title}"?`)) deleteMutation.mutate(sourceId)
  }

  const canAdd = form.title.trim() !== '' && form.content.trim() !== ''

  return (
    <div className="space-y-6">
      <section className="space-y-2">
        <p className="text-textSecondary text-xs">
          {plural(pack.sources.length, 'source')}. Draft with AI writes key points from these texts, and source quotes
          are checked against them.
        </p>
        {deleteMutation.isError && (
          <Notice tone="error">Could not delete: {apiErrorDetail(deleteMutation.error)}</Notice>
        )}
        {pack.sources.length === 0 ? (
          <div className="bg-card/50 border border-dashed border-white/10 rounded-xl p-6 text-center">
            <p className="text-gray-400 text-sm">No sources yet</p>
            <p className="text-gray-500 text-xs mt-1">
              Paste official documentation, internal notes or articles the answer key should follow.
            </p>
          </div>
        ) : (
          pack.sources.map((source) => {
            const deleting = deleteMutation.isPending && deleteMutation.variables === source.id
            return (
              <div key={source.id} className="bg-card border border-cardBorder rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-textPrimary">{source.title}</p>
                    <p className="text-xs text-textSecondary mt-0.5">
                      {source.content_length.toLocaleString()} characters
                      {source.url && (
                        <>
                          {' - '}
                          <a
                            href={source.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-accent hover:underline break-all"
                          >
                            {source.url}
                          </a>
                        </>
                      )}
                    </p>
                  </div>
                  <button
                    type="button"
                    className={dangerButtonClass}
                    disabled={deleting}
                    onClick={() => handleDelete(source.id, source.title)}
                  >
                    {deleting && <Spinner />}
                    Delete
                  </button>
                </div>
                {source.preview && (
                  <p className="text-xs text-gray-400 mt-2 line-clamp-3 whitespace-pre-line">{source.preview}</p>
                )}
              </div>
            )
          })
        )}
      </section>

      <section className={cardClass}>
        <h3 className="text-sm font-semibold text-textPrimary mb-3">Add source</h3>
        <fieldset disabled={addMutation.isPending} className="space-y-3 min-w-0">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Field label="Title">
              <input
                type="text"
                maxLength={200}
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="e.g. PostgreSQL docs: Indexes"
                className={inputClass}
              />
            </Field>
            <Field label="URL (optional)">
              <input
                type="url"
                maxLength={500}
                value={form.url}
                onChange={(e) => setForm({ ...form, url: e.target.value })}
                placeholder="https://"
                className={inputClass}
              />
            </Field>
          </div>
          <Field
            label="Content"
            hint={`${form.content.length.toLocaleString()} / ${MAX_SOURCE_CHARS.toLocaleString()} characters`}
          >
            <textarea
              rows={10}
              maxLength={MAX_SOURCE_CHARS}
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
              placeholder="Paste the source text"
              className={`${inputClass} font-mono text-xs`}
            />
          </Field>
          {addMutation.isError && <Notice tone="error">Could not add source: {apiErrorDetail(addMutation.error)}</Notice>}
          <button type="button" className={primaryButtonClass} disabled={!canAdd} onClick={handleAdd}>
            {addMutation.isPending ? <Spinner /> : <PlusIcon />}
            Add source
          </button>
        </fieldset>
      </section>
    </div>
  )
}
