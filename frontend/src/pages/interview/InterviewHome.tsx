import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createInterviewPack, fetchInterviewPacks, importInterviewPack } from '../../api/interview'
import { NewPackForm } from '../../components/interview/NewPackForm'
import { PackCard } from '../../components/interview/PackCard'
import { outlineButtonClass } from '../../components/interview/ui'
import { apiErrorDetail } from '../../components/interview/utils'
import { createLogger, errorData } from '../../lib/log'
import type { InterviewPackSummary } from '../../types/interview'

const log = createLogger('interview/home')

export function InterviewHome() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [showNewPack, setShowNewPack] = useState(false)

  const { data: packs, isLoading, isError, error } = useQuery<InterviewPackSummary[]>({
    queryKey: ['interview', 'packs'],
    queryFn: fetchInterviewPacks,
    staleTime: 0,
  })

  const importMutation = useMutation({
    mutationFn: (file: File) => {
      log.info('pack import start', { name: file.name, bytes: file.size })
      return importInterviewPack(file)
    },
    onSuccess: (pack) => {
      log.info('pack import ok', {
        packId: pack.id,
        title: pack.title,
        version: pack.version,
        questions: pack.questions.length,
        glossary: pack.glossary.length,
      })
      void queryClient.invalidateQueries({ queryKey: ['interview'] })
      navigate(`/interview/packs/${pack.id}`)
    },
    onError: (err) => log.error('pack import failed', errorData(err)),
  })

  const createMutation = useMutation({
    mutationFn: createInterviewPack,
    onSuccess: (pack) => {
      void queryClient.invalidateQueries({ queryKey: ['interview', 'packs'] })
      navigate(`/interview/packs/${pack.id}/studio`)
    },
  })

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (file) importMutation.mutate(file)
  }

  return (
    <div className="flex flex-col min-h-screen">
      <div className="bg-sidebar border-b border-cardBorder px-6 py-4 sticky top-0 z-10 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-textPrimary font-semibold text-lg leading-tight">Interview Practice</h1>
          <p className="text-textSecondary text-xs mt-0.5">Answer technical interview questions out loud in English</p>
        </div>
        <div className="flex items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".json,application/json"
            onChange={handleFileChange}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={importMutation.isPending}
            className={outlineButtonClass}
          >
            {importMutation.isPending ? 'Importing...' : 'Import pack'}
          </button>
          <button
            onClick={() => setShowNewPack(true)}
            className="px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-purple-600 text-white font-semibold text-sm hover:opacity-90 transition-opacity"
          >
            New pack
          </button>
        </div>
      </div>

      <div className="p-6 flex-1 space-y-6">
        {importMutation.isError && (
          <div className="bg-red-900/20 border border-red-500/30 rounded-xl p-4 flex items-start justify-between gap-4">
            <div>
              <p className="text-red-400 text-sm font-medium">Could not import this pack file</p>
              <p className="text-red-400/80 text-xs mt-1 whitespace-pre-line break-words">
                {apiErrorDetail(importMutation.error)}
              </p>
            </div>
            <button
              onClick={() => importMutation.reset()}
              className="text-xs text-red-400/80 hover:text-red-300 shrink-0"
            >
              Dismiss
            </button>
          </div>
        )}

        {showNewPack && (
          <NewPackForm
            submitting={createMutation.isPending}
            error={createMutation.isError ? apiErrorDetail(createMutation.error) : null}
            onSubmit={(input) => createMutation.mutate(input)}
            onCancel={() => {
              setShowNewPack(false)
              createMutation.reset()
            }}
          />
        )}

        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-44 bg-card animate-pulse rounded-xl" />
            ))}
          </div>
        ) : isError ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <p className="text-red-400 text-lg">Could not load interview packs</p>
            <p className="text-textSecondary text-sm mt-2">{apiErrorDetail(error)}</p>
          </div>
        ) : !packs || packs.length === 0 ? (
          <div className="bg-card/50 border border-dashed border-white/10 rounded-xl p-10 text-center max-w-2xl mx-auto">
            <p className="text-textPrimary font-medium">No interview packs yet</p>
            <p className="text-textSecondary text-sm mt-2 leading-relaxed">
              A senior developer or coach prepares a pack for a client interview: the questions, the approved
              key points a good answer must cover, common misconceptions and follow-up questions. Import the pack
              file they shared with you, or create a new pack and build it in Pack Studio.
            </p>
            <div className="mt-5 flex items-center justify-center gap-2">
              <button
                onClick={() => fileInputRef.current?.click()}
                className={outlineButtonClass}
              >
                Import pack
              </button>
              <button
                onClick={() => setShowNewPack(true)}
                className="px-4 py-2 rounded-lg bg-accent/10 text-accent border border-accent/30 text-sm hover:bg-accent/20 transition-colors"
              >
                New pack
              </button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {packs.map((pack) => (
              <PackCard key={pack.id} pack={pack} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
