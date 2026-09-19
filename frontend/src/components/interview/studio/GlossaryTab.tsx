import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { replaceInterviewGlossary } from '../../../api/interview'
import type { InterviewGlossaryTerm, InterviewPackDetail } from '../../../types/interview'
import { apiErrorDetail } from '../utils'
import {
  glossaryErrors,
  glossaryToRows,
  isGlossaryDirty,
  newUid,
  plural,
  rowsToGlossary,
  type GlossaryRow,
} from './studioModel'
import {
  IssueList,
  Notice,
  PlusIcon,
  RemoveButton,
  Spinner,
  cardClass,
  inputClass,
  primaryButtonClass,
  secondaryButtonClass,
} from './studioUi'

interface GlossaryTabProps {
  pack: InterviewPackDetail
  onDirtyChange: (dirty: boolean) => void
}

export function GlossaryTab({ pack, onDirtyChange }: GlossaryTabProps) {
  const queryClient = useQueryClient()
  const [rows, setRows] = useState<GlossaryRow[] | null>(null)
  const currentRows = rows ?? glossaryToRows(pack.glossary)
  const dirty = isGlossaryDirty(rows, pack.glossary)
  const errors = glossaryErrors(currentRows)

  useEffect(() => onDirtyChange(dirty), [dirty, onDirtyChange])

  const saveMutation = useMutation({
    mutationFn: (terms: InterviewGlossaryTerm[]) => replaceInterviewGlossary(pack.id, terms),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['interview'] })
      setRows(null)
    },
  })

  function update(key: string, patch: Partial<GlossaryRow>) {
    setRows(currentRows.map((row) => (row.key === key ? { ...row, ...patch } : row)))
  }

  return (
    <div className={cardClass}>
      <p className="text-sm text-textSecondary">
        Technical terms the speech recognizer tends to mishear. Transcripts are corrected to the exact spelling before
        review. Aliases are extra spoken forms, separated by commas (e.g. PostgreSQL: post gres, postgres).
      </p>

      <fieldset disabled={saveMutation.isPending} className="mt-4 space-y-2 min-w-0">
        {currentRows.length > 0 && (
          <div className="hidden md:grid grid-cols-[14rem_1fr_2rem] gap-2 text-xs font-medium text-textSecondary">
            <span>Term</span>
            <span>Aliases</span>
          </div>
        )}
        {currentRows.map((row) => (
          <div key={row.key} className="grid grid-cols-[1fr_2rem] md:grid-cols-[14rem_1fr_2rem] gap-2 items-center">
            <input
              type="text"
              maxLength={100}
              value={row.term}
              onChange={(e) => update(row.key, { term: e.target.value })}
              placeholder="Databricks"
              aria-label="Term"
              className={`${inputClass} col-span-1`}
            />
            <input
              type="text"
              value={row.aliases}
              onChange={(e) => update(row.key, { aliases: e.target.value })}
              placeholder="data bricks, data brick"
              aria-label="Aliases"
              className={`${inputClass} col-span-1 row-start-2 md:row-start-auto`}
            />
            <span className="row-span-2 md:row-span-1 flex justify-center">
              <RemoveButton
                label="Remove term"
                onClick={() => setRows(currentRows.filter((item) => item.key !== row.key))}
              />
            </span>
          </div>
        ))}

        <button
          type="button"
          className={secondaryButtonClass}
          onClick={() => setRows([...currentRows, { key: newUid(), term: '', aliases: '' }])}
        >
          <PlusIcon /> Add term
        </button>

        <IssueList tone="error" issues={errors} />
        {saveMutation.isError && <Notice tone="error">Could not save: {apiErrorDetail(saveMutation.error)}</Notice>}

        <div className="flex flex-wrap items-center gap-2 pt-2">
          <button
            type="button"
            className={primaryButtonClass}
            disabled={!dirty || errors.length > 0}
            onClick={() => saveMutation.mutate(rowsToGlossary(currentRows))}
          >
            {saveMutation.isPending && <Spinner />}
            Save glossary
          </button>
          {dirty && (
            <button type="button" className={secondaryButtonClass} onClick={() => setRows(null)}>
              Discard changes
            </button>
          )}
          <span className="ml-auto text-xs text-textSecondary">{plural(pack.glossary.length, 'saved term')}</span>
        </div>
      </fieldset>
    </div>
  )
}
