import type { InterviewTopicReadiness } from '../../types/interview'
import { bandStyle, scoreBand, topicLabel } from './utils'

export function TopicReadiness({ topics }: { topics: InterviewTopicReadiness[] }) {
  return (
    <div className="bg-card border border-cardBorder rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <p className="text-textPrimary font-semibold text-sm">Readiness by topic</p>
        <p className="text-textSecondary text-xs">Latest content score per question</p>
      </div>
      {topics.length === 0 ? (
        <p className="text-textSecondary text-sm">No topics yet.</p>
      ) : (
        <div className="space-y-3">
          {topics.map((topic) => {
            const average = topic.average_content_score === null ? null : Math.round(topic.average_content_score)
            const style = bandStyle(scoreBand(average))
            return (
              <div key={topic.topic}>
                <div className="flex items-center justify-between gap-3 text-sm">
                  <span className="text-textPrimary truncate">{topicLabel(topic.topic)}</span>
                  <span className="text-textSecondary text-xs shrink-0">
                    {topic.graded_count}/{topic.question_count} graded
                    <span className={`ml-2 font-semibold ${average === null ? 'text-textSecondary' : style.text}`}>
                      {average ?? '--'}
                    </span>
                  </span>
                </div>
                <div className="mt-1.5 h-1.5 w-full bg-background rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${style.bar}`}
                    style={{ width: `${average ?? 0}%` }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
