import { interviewPackExportUrl, interviewPackReportUrl } from '../../../api/interview'
import type { InterviewPackDetail } from '../../../types/interview'
import { plural } from './studioModel'
import { Notice, cardClass, primaryButtonClass, secondaryButtonClass } from './studioUi'

interface ExportTabProps {
  pack: InterviewPackDetail
  hasUnsavedChanges: boolean
}

export function ExportTab({ pack, hasUnsavedChanges }: ExportTabProps) {
  return (
    <div className="space-y-4">
      {hasUnsavedChanges && (
        <Notice tone="warning">
          You have unsaved changes in the questionnaire editor. Save them first to include them in the file.
        </Notice>
      )}

      <div className={cardClass}>
        <h3 className="text-sm font-semibold text-textPrimary">Questionnaire file</h3>
        <p className="text-sm text-textSecondary mt-1">
          Version v{pack.version} with {plural(pack.questions.length, 'question')},{' '}
          {plural(pack.sources.length, 'source')} and {plural(pack.glossary.length, 'glossary term')}. Candidates
          upload this JSON file from the Interview page; uploading a newer version of the same questionnaire
          updates it in place and keeps their answers.
        </p>
        <a href={interviewPackExportUrl(pack.id)} download className={`${primaryButtonClass} mt-4`}>
          Download questionnaire file
        </a>
      </div>

      <div className={cardClass}>
        <h3 className="text-sm font-semibold text-textPrimary">Practice results</h3>
        <p className="text-sm text-textSecondary mt-1">
          Every answer recorded on this computer with transcripts, scores and key point results, for reviewing a
          candidate&apos;s progress.
        </p>
        <a href={interviewPackReportUrl(pack.id)} download className={`${secondaryButtonClass} mt-4`}>
          Download results
        </a>
      </div>
    </div>
  )
}
