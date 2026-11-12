import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchCandidateProfile, readCvFile, saveCandidateProfile } from '../../api/interview'
import { createLogger, errorData } from '../../lib/log'
import { apiErrorDetail, plural } from '../../components/interview/utils'
import {
  Field,
  Notice,
  Spinner,
  cardClass,
  inputClass,
  primaryButtonClass,
  secondaryButtonClass,
} from '../../components/interview/studio/studioUi'
import type { CandidateProfileInput, CandidateProfileSaved } from '../../types/interview'

const log = createLogger('interview/cv')

export const CV_FILE_ACCEPT = '.pdf,.docx,.txt,.md,.markdown,.rst'
export const CV_TEXT_MAX = 60_000
const EMPTY: CandidateProfileInput = { target_role: '', cv_text: '', cv_filename: '' }

export function savedMessage(saved: CandidateProfileSaved): string {
  if (saved.introductions_retired === 0 && !saved.introduction_written) return 'Saved.'
  const retired =
    saved.introductions_retired > 0
      ? ` ${plural(saved.introductions_retired, 'introduction question')} from the old CV retired.`
      : ''
  const written = !saved.introduction_written
    ? ' Write a new one on the CV tab when the quota allows.'
    : saved.introductions_retired > 0
      ? ' A new one was written from this CV.'
      : ' An introduction question was written from this CV.'
  return `Saved.${retired}${written}`
}

export function CandidateCv() {
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [form, setForm] = useState<CandidateProfileInput | null>(null)

  const { data: profile, isLoading } = useQuery({
    queryKey: ['interview', 'profile'],
    queryFn: fetchCandidateProfile,
  })

  useEffect(() => {
    if (profile && form === null) {
      setForm({
        target_role: profile.target_role,
        cv_text: profile.cv_text,
        cv_filename: profile.cv_filename,
      })
    }
  }, [profile, form])

  const current = form ?? EMPTY

  const readMutation = useMutation({
    mutationFn: (file: File) => {
      log.info('cv file read start', { name: file.name, bytes: file.size })
      return readCvFile(file)
    },
    onSuccess: (result) => {
      log.info('cv file read ok', { name: result.filename, characters: result.characters })
      setForm({ ...current, cv_text: result.text, cv_filename: result.filename })
    },
    onError: (error) => log.error('cv file read failed', errorData(error)),
  })

  const saveMutation = useMutation({
    mutationFn: (input: CandidateProfileInput) => saveCandidateProfile(input),
    // A changed CV retires the old introductions and writes a new one, so every interview list is stale.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['interview'] }),
  })

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (file) readMutation.mutate(file)
  }

  const characters = current.cv_text.length

  return (
    <div className="flex flex-col min-h-screen">
      <div className="bg-sidebar border-b border-cardBorder px-6 py-4 sticky top-0 z-10 flex items-center gap-2 text-sm text-textSecondary">
        <Link to="/interview?tab=cv" className="hover:text-textPrimary transition-colors">
          Interview
        </Link>
        <span className="text-[10px]">/</span>
        <span className="text-textPrimary font-medium">My CV</span>
      </div>

      <div className="p-6 flex-1 space-y-4 max-w-3xl w-full mx-auto">
        {isLoading ? (
          <div className="h-80 bg-card animate-pulse rounded-xl" />
        ) : (
          <div className={cardClass}>
            <fieldset disabled={saveMutation.isPending || readMutation.isPending} className="space-y-4 min-w-0">
              <Field label="Role you are interviewing for">
                <input
                  type="text"
                  maxLength={120}
                  value={current.target_role}
                  onChange={(e) => setForm({ ...current, target_role: e.target.value })}
                  placeholder="e.g. Senior data engineer"
                  className={inputClass}
                />
              </Field>

              <Field
                label="CV"
                hint={`${characters.toLocaleString()} / ${CV_TEXT_MAX.toLocaleString()} characters${
                  current.cv_filename ? ` - from ${current.cv_filename}` : ''
                }`}
              >
                <textarea
                  rows={18}
                  maxLength={CV_TEXT_MAX}
                  value={current.cv_text}
                  onChange={(e) => setForm({ ...current, cv_text: e.target.value })}
                  placeholder="Upload your CV, or paste it here"
                  className={`${inputClass} font-mono text-xs`}
                />
              </Field>

              <div className="flex flex-wrap items-center gap-3">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={CV_FILE_ACCEPT}
                  onChange={handleFileChange}
                  className="hidden"
                />
                <button type="button" className={secondaryButtonClass} onClick={() => fileInputRef.current?.click()}>
                  {readMutation.isPending && <Spinner />}
                  {readMutation.isPending ? 'Reading...' : 'Upload a CV file'}
                </button>
                <div className="flex-1" />
                <button
                  type="button"
                  className={primaryButtonClass}
                  disabled={characters === 0}
                  onClick={() => saveMutation.mutate(current)}
                >
                  {saveMutation.isPending && <Spinner />}
                  Save
                </button>
              </div>
            </fieldset>

            {readMutation.isError && <Notice tone="error">{apiErrorDetail(readMutation.error)}</Notice>}
            {readMutation.isSuccess && readMutation.data.truncated && (
              <Notice tone="warning">
                The file was cut to the first {CV_TEXT_MAX.toLocaleString()} characters.
              </Notice>
            )}
            {saveMutation.isError && (
              <Notice tone="error">Could not save: {apiErrorDetail(saveMutation.error)}</Notice>
            )}
            {saveMutation.isSuccess && (
              <Notice tone="success">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="flex-1">{savedMessage(saveMutation.data)}</span>
                  <Link to="/interview?tab=cv" className={secondaryButtonClass}>
                    Back to interview
                  </Link>
                </div>
              </Notice>
            )}
          </div>
        )}

      </div>
    </div>
  )
}
