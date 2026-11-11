import { useQuery } from '@tanstack/react-query'
import { useCallback, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { fetchInterviewPack } from '../../api/interview'
import { DetailsTab } from '../../components/interview/studio/DetailsTab'
import { DraftTab } from '../../components/interview/studio/DraftTab'
import { ExportTab } from '../../components/interview/studio/ExportTab'
import { GlossaryTab } from '../../components/interview/studio/GlossaryTab'
import { QuestionsTab } from '../../components/interview/studio/QuestionsTab'
import { SourcesTab } from '../../components/interview/studio/SourcesTab'
import type { StudioTab } from '../../components/interview/studio/studioModel'
import { outlineButtonClass } from '../../components/interview/ui'
import { apiErrorDetail } from '../../components/interview/utils'
import { useUnsavedChangesGuard } from '../../hooks/useUnsavedChangesGuard'
import type { InterviewPackDetail } from '../../types/interview'

const TABS: { id: StudioTab; label: string }[] = [
  { id: 'details', label: 'Details' },
  { id: 'sources', label: 'Sources' },
  { id: 'draft', label: 'Draft with AI' },
  { id: 'questions', label: 'Questions' },
  { id: 'glossary', label: 'Glossary' },
  { id: 'export', label: 'Download' },
]

function isStudioTab(value: string | null): value is StudioTab {
  return TABS.some((tab) => tab.id === value)
}

export function PackStudio() {
  const { packId: packIdStr } = useParams<{ packId: string }>()
  const packId = Number(packIdStr)
  const [searchParams, setSearchParams] = useSearchParams()
  const tabParam = searchParams.get('tab')
  const activeTab: StudioTab = isStudioTab(tabParam) ? tabParam : 'questions'
  const [dirtyTabs, setDirtyTabs] = useState<Partial<Record<StudioTab, boolean>>>({})
  const [draftedIds, setDraftedIds] = useState<number[]>([])

  const { data: pack, isLoading, isError, error } = useQuery<InterviewPackDetail>({
    queryKey: ['interview', 'pack', packId],
    queryFn: () => fetchInterviewPack(packId),
    enabled: !isNaN(packId),
    staleTime: 0,
  })

  const markDirty = useCallback((tab: StudioTab, dirty: boolean) => {
    setDirtyTabs((prev) => (!!prev[tab] === dirty ? prev : { ...prev, [tab]: dirty }))
  }, [])

  const dirtyHandlers = useMemo(
    () => ({
      details: (dirty: boolean) => markDirty('details', dirty),
      sources: (dirty: boolean) => markDirty('sources', dirty),
      questions: (dirty: boolean) => markDirty('questions', dirty),
      glossary: (dirty: boolean) => markDirty('glossary', dirty),
    }),
    [markDirty],
  )

  const selectTab = useCallback(
    (tab: StudioTab) => setSearchParams({ tab }, { replace: true }),
    [setSearchParams],
  )

  const hasUnsavedChanges = Object.values(dirtyTabs).some(Boolean)
  useUnsavedChangesGuard(hasUnsavedChanges, 'The questionnaire editor has unsaved changes. Leave without saving them?')

  function panelClass(tab: StudioTab): string {
    return activeTab === tab ? '' : 'hidden'
  }

  return (
    <div className="flex flex-col min-h-screen">
      <div className="bg-sidebar border-b border-cardBorder px-6 py-4 sticky top-0 z-10 space-y-3">
        <div className="flex items-center gap-2 text-sm text-textSecondary">
          <Link to="/interview" className="hover:text-textPrimary transition-colors shrink-0">
            Interview
          </Link>
          <span className="text-[10px]">/</span>
          {pack ? (
            <Link
              to={`/interview/packs/${pack.id}`}
              className="hover:text-textPrimary transition-colors line-clamp-1"
            >
              {pack.title}
            </Link>
          ) : (
            <span className="line-clamp-1">{isLoading ? 'Loading...' : 'Questionnaire'}</span>
          )}
          <span className="text-[10px]">/</span>
          <span className="text-textPrimary font-medium shrink-0">Edit questionnaire</span>
          {hasUnsavedChanges && (
            <span className="ml-auto text-xs text-amber-300 border border-amber-500/30 bg-amber-500/10 rounded-full px-2 py-0.5 shrink-0">
              Unsaved changes
            </span>
          )}
        </div>

        {pack && (
          <div
            role="tablist"
            aria-label="Questionnaire editor sections"
            className="flex items-center gap-1 bg-background rounded-lg p-1 w-fit max-w-full overflow-x-auto"
          >
            {TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={activeTab === tab.id}
                onClick={() => selectTab(tab.id)}
                className={[
                  'relative px-4 py-1.5 rounded-md text-sm font-medium whitespace-nowrap transition-colors duration-150',
                  activeTab === tab.id ? 'bg-card text-textPrimary shadow' : 'text-textSecondary hover:text-textPrimary',
                ].join(' ')}
              >
                {tab.label}
                {tab.id === 'questions' && ` (${pack.questions.length})`}
                {dirtyTabs[tab.id] && (
                  <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-amber-400" title="Unsaved changes" />
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="p-6 flex-1 max-w-5xl w-full mx-auto">
        {isLoading ? (
          <div className="space-y-4">
            <div className="h-24 bg-card animate-pulse rounded-xl" />
            <div className="h-40 bg-card animate-pulse rounded-xl" />
            <div className="h-40 bg-card animate-pulse rounded-xl" />
          </div>
        ) : isError || isNaN(packId) || !pack ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <p className="text-red-400 text-lg">Could not load this questionnaire</p>
            <p className="text-textSecondary text-sm mt-2">
              {isNaN(packId) ? 'Invalid questionnaire link.' : apiErrorDetail(error)}
            </p>
            <Link to="/interview" className={`mt-4 ${outlineButtonClass}`}>
              Back to questionnaires
            </Link>
          </div>
        ) : (
          <>
            <div className={panelClass('details')}>
              <DetailsTab pack={pack} onDirtyChange={dirtyHandlers.details} />
            </div>
            <div className={panelClass('sources')}>
              <SourcesTab pack={pack} onDirtyChange={dirtyHandlers.sources} />
            </div>
            <div className={panelClass('draft')}>
              <DraftTab pack={pack} onDrafted={(ids) => setDraftedIds((prev) => [...prev, ...ids])} onOpenTab={selectTab} />
            </div>
            <div className={panelClass('questions')}>
              <QuestionsTab
                pack={pack}
                draftedIds={draftedIds}
                onDirtyChange={dirtyHandlers.questions}
                onOpenTab={selectTab}
              />
            </div>
            <div className={panelClass('glossary')}>
              <GlossaryTab pack={pack} onDirtyChange={dirtyHandlers.glossary} />
            </div>
            <div className={panelClass('export')}>
              <ExportTab pack={pack} hasUnsavedChanges={hasUnsavedChanges} />
            </div>
          </>
        )}
      </div>
    </div>
  )
}
