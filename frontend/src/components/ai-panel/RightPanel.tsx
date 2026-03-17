import type { Attempt, Question } from '../../types'
import { PronunciationRightPanel } from './PronunciationRightPanel'
import { RightPanelPlaceholder } from './RightPanelPlaceholder'

export function RightPanel({
  question,
  pronunAttempt,
  onClose,
  allQuestions,
}: {
  question: Question | null
  pronunAttempt: Attempt | null
  onClose: () => void
  allQuestions: Question[]
}) {
  return (
    <div className="right-panel flex flex-col h-full">
      {pronunAttempt ? (
        <PronunciationRightPanel attempt={pronunAttempt} onClose={onClose} />
      ) : (
        <RightPanelPlaceholder question={question} allQuestions={allQuestions} />
      )}
    </div>
  )
}
