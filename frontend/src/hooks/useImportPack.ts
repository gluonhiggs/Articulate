import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { importInterviewPack } from '../api/interview'
import { createLogger, errorData } from '../lib/log'

const log = createLogger('interview/import')

export const PACK_FILE_ACCEPT = '.json,application/json'

/**
 * Importing a pack file, shared by every page that offers it.
 *
 * Each page renders its own button and its own error, which differ by layout, but the
 * mutation, the logging and the navigation live here so two copies cannot drift apart.
 */
export function useImportPack() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)

  const mutation = useMutation({
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

  function onFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    // Cleared so picking the same file twice still fires a change event.
    event.target.value = ''
    if (file) mutation.mutate(file)
  }

  return {
    inputRef,
    onFileChange,
    open: () => inputRef.current?.click(),
    pending: mutation.isPending,
    error: mutation.isError ? mutation.error : null,
    reset: () => mutation.reset(),
  }
}
