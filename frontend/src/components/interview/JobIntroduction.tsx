import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { draftJobIntroduction, fetchCandidateProfile } from '../../api/interview'
import { createLogger, errorData } from '../../lib/log'
import { outlineButtonClass } from './ui'
import { apiErrorDetail } from './utils'

const log = createLogger('interview/job-introduction')

export function JobIntroduction({ packId, hasIntroduction }: { packId: number; hasIntroduction: boolean }) {
  const queryClient = useQueryClient()
  const { data: profile } = useQuery({ queryKey: ['interview', 'profile'], queryFn: fetchCandidateProfile })
  const hasCv = profile?.has_cv ?? false

  const draftMutation = useMutation({
    mutationFn: () => {
      log.info('job introduction start', { packId })
      return draftJobIntroduction(packId)
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['interview'] }),
    onError: (error) => log.error('job introduction failed', errorData(error)),
  })

  return (
    <div className="flex flex-wrap items-center gap-3 bg-card border border-cardBorder rounded-xl px-4 py-3">
      <div className="flex-1 min-w-0">
        <p className="text-sm text-textPrimary">Introduce yourself for this job</p>
        <p className="text-xs text-textSecondary mt-0.5">
          {hasCv
            ? 'One question from your CV, aimed at this job. It is added under About you below.'
            : 'Add your CV first, so the question can be about your own projects.'}
        </p>
        {draftMutation.isError && <p className="text-red-400 text-xs mt-1">{apiErrorDetail(draftMutation.error)}</p>}
      </div>
      {hasCv ? (
        <button
          type="button"
          onClick={() => draftMutation.mutate()}
          disabled={draftMutation.isPending}
          className={outlineButtonClass}
        >
          {draftMutation.isPending ? 'Writing...' : hasIntroduction ? 'Write another' : 'Write it'}
        </button>
      ) : (
        <Link to="/interview/cv" className={outlineButtonClass}>
          Add my CV
        </Link>
      )}
    </div>
  )
}
