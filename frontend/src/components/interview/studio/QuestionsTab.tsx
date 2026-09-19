import { useEffect, useId, useMemo, useState } from 'react'
import type { InterviewPackDetail, InterviewQuestionInput } from '../../../types/interview'
import { groupByTopic } from '../utils'
import { QuestionEditor } from './QuestionEditor'
import {
  isQuestionDirty,
  needsReview,
  newQuestionInput,
  newUid,
  plural,
  questionToInput,
  uniqueTopics,
  withoutKey,
  type StudioTab,
} from './studioModel'
import { PlusIcon, Toggle, primaryButtonClass, secondaryButtonClass } from './studioUi'

interface NewQuestionDraft {
  key: string
  input: InterviewQuestionInput
}

interface QuestionsTabProps {
  pack: InterviewPackDetail
  draftedIds: number[]
  onDirtyChange: (dirty: boolean) => void
  onOpenTab: (tab: StudioTab) => void
}

export function QuestionsTab({ pack, draftedIds, onDirtyChange, onOpenTab }: QuestionsTabProps) {
  const topicsListId = useId()
  const [drafts, setDrafts] = useState<Record<number, InterviewQuestionInput>>({})
  const [newDrafts, setNewDrafts] = useState<NewQuestionDraft[]>([])
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [reviewOnly, setReviewOnly] = useState(false)

  const dirtyIds = useMemo(
    () => new Set(pack.questions.filter((q) => isQuestionDirty(q, drafts[q.id])).map((q) => q.id)),
    [pack.questions, drafts],
  )
  const reviewIds = useMemo(
    () => new Set(pack.questions.filter((q) => needsReview(questionToInput(q))).map((q) => q.id)),
    [pack.questions],
  )
  const topics = useMemo(() => uniqueTopics(pack.questions), [pack.questions])

  const tabDirty = newDrafts.length > 0 || dirtyIds.size > 0
  useEffect(() => onDirtyChange(tabDirty), [tabDirty, onDirtyChange])

  const visibleQuestions = reviewOnly
    ? pack.questions.filter((q) => reviewIds.has(q.id) || dirtyIds.has(q.id))
    : pack.questions
  const groups = groupByTopic(visibleQuestions)

  function toggleExpanded(key: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  function addQuestion() {
    const key = newUid()
    setNewDrafts((prev) => [{ key, input: newQuestionInput() }, ...prev])
    setExpanded((prev) => new Set(prev).add(`new-${key}`))
  }

  function updateNewDraft(key: string, input: InterviewQuestionInput) {
    setNewDrafts((prev) => prev.map((draft) => (draft.key === key ? { key, input } : draft)))
  }

  function removeNewDraft(key: string) {
    setNewDrafts((prev) => prev.filter((draft) => draft.key !== key))
  }

  function clearDraft(questionId: number) {
    setDrafts((prev) => withoutKey(prev, questionId))
  }

  if (pack.questions.length === 0 && newDrafts.length === 0) {
    return (
      <div className="bg-card/50 border border-dashed border-white/10 rounded-xl p-8 text-center">
        <p className="text-gray-400 text-sm">No questions yet</p>
        <p className="text-gray-500 text-xs mt-1 max-w-md mx-auto">
          Write questions yourself, or add sources and let AI draft them. Review and approve every key point before
          candidates practice: unapproved key points are never graded.
        </p>
        <div className="flex flex-wrap justify-center gap-2 mt-4">
          <button type="button" className={primaryButtonClass} onClick={addQuestion}>
            <PlusIcon /> New question
          </button>
          <button type="button" className={secondaryButtonClass} onClick={() => onOpenTab('draft')}>
            Draft with AI
          </button>
          <button type="button" className={secondaryButtonClass} onClick={() => onOpenTab('sources')}>
            Add sources
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <datalist id={topicsListId}>
        {topics.map((topic) => (
          <option key={topic} value={topic} />
        ))}
      </datalist>

      <div className="flex flex-wrap items-center gap-4">
        <p className="text-textSecondary text-xs flex-1">
          {plural(pack.questions.length, 'question')}
          {reviewIds.size > 0 && ` - ${reviewIds.size} need review`}
        </p>
        <Toggle checked={reviewOnly} onChange={setReviewOnly} label="Needs review only" />
        <button type="button" className={primaryButtonClass} onClick={addQuestion}>
          <PlusIcon /> New question
        </button>
      </div>

      {newDrafts.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-textSecondary">New questions</h3>
          {newDrafts.map((draft) => (
            <QuestionEditor
              key={draft.key}
              packId={pack.id}
              saved={null}
              input={draft.input}
              dirty
              expanded={expanded.has(`new-${draft.key}`)}
              justDrafted={false}
              topicsListId={topicsListId}
              onToggle={() => toggleExpanded(`new-${draft.key}`)}
              onChange={(input) => updateNewDraft(draft.key, input)}
              onDiscard={() => removeNewDraft(draft.key)}
              onSaved={(question) => {
                removeNewDraft(draft.key)
                setExpanded((prev) => new Set(prev).add(`saved-${question.id}`))
              }}
              onRetired={() => removeNewDraft(draft.key)}
            />
          ))}
        </section>
      )}

      {reviewOnly && groups.length === 0 && (
        <p className="text-textSecondary text-sm text-center py-8">Every question is reviewed and approved.</p>
      )}

      {groups.map((group) => (
        <section key={group.topic} className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-textSecondary">
            {group.topic} <span className="font-normal">({group.items.length})</span>
          </h3>
          {group.items.map((question) => (
            <QuestionEditor
              key={question.id}
              packId={pack.id}
              saved={question}
              input={drafts[question.id] ?? questionToInput(question)}
              dirty={dirtyIds.has(question.id)}
              expanded={expanded.has(`saved-${question.id}`)}
              justDrafted={draftedIds.includes(question.id)}
              topicsListId={topicsListId}
              onToggle={() => toggleExpanded(`saved-${question.id}`)}
              onChange={(input) => setDrafts((prev) => ({ ...prev, [question.id]: input }))}
              onDiscard={() => clearDraft(question.id)}
              onSaved={() => clearDraft(question.id)}
              onRetired={() => clearDraft(question.id)}
            />
          ))}
        </section>
      ))}
    </div>
  )
}
