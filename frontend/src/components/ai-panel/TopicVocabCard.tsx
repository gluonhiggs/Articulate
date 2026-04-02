import type { VocabItem } from '../../types'
import type { TopicVocabFeedItem } from './feedTypes'

function LoadingRow({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-2 py-3">
      <div className="animate-spin h-4 w-4 border-2 border-teal-400 border-t-transparent rounded-full shrink-0" />
      <span className="text-gray-400 text-sm">{text}</span>
    </div>
  )
}

export function TopicVocabCard({
  item,
  onDismiss,
}: {
  item: TopicVocabFeedItem
  onDismiss: () => void
}) {
  return (
    <div className="mb-4 rounded-xl bg-white/[0.03] border border-white/5 overflow-hidden">
      {/* Card header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/5">
        <span className="text-xs text-gray-500 uppercase tracking-wider">Topic Vocabulary (Band 8-9)</span>
        <button
          onClick={onDismiss}
          className="w-5 h-5 rounded-full border border-white/10 flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
          aria-label="Dismiss"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-2.5 w-2.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      {/* Card body */}
      <div className="p-4">
        {item.loading ? (
          <LoadingRow text="Generating vocabulary..." />
        ) : item.error ? (
          <div className="rounded-lg bg-red-500/10 border border-red-500/20 p-3">
            <p className="text-red-400 text-sm">{item.error}</p>
          </div>
        ) : item.vocabData ? (
          <div className="space-y-2">
            {item.vocabData.vocabulary.map((v: VocabItem, i: number) => (
              <div key={i} className="rounded-lg bg-white/[0.03] border border-white/5 p-3">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-medium text-teal-300">{v.term}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-gray-500 border border-white/10">
                    {(v.type ?? '').replace('_', ' ')}
                  </span>
                </div>
                <p className="text-xs text-gray-400 mb-1">{v.definition}</p>
                <p className="text-xs text-gray-500 italic">&ldquo;{v.example}&rdquo;</p>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}
