import type { SampleAnswerFeedItem } from './feedTypes'

function LoadingRow({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-2 py-3">
      <div className="animate-spin h-4 w-4 border-2 border-teal-400 border-t-transparent rounded-full shrink-0" />
      <span className="text-gray-400 text-sm">{text}</span>
    </div>
  )
}

export function SampleAnswerCard({
  item,
  onDismiss,
}: {
  item: SampleAnswerFeedItem
  onDismiss: () => void
}) {
  return (
    <div className="mb-4 rounded-xl bg-white/[0.03] border border-white/5 overflow-hidden">
      {/* Card header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/5">
        <span className="text-xs text-gray-500 uppercase tracking-wider">Sample Answer (Band 7)</span>
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
          <LoadingRow text="Generating sample answer..." />
        ) : item.error ? (
          <div className="rounded-lg bg-red-500/10 border border-red-500/20 p-3">
            <p className="text-red-400 text-sm">{item.error}</p>
          </div>
        ) : item.data ? (
          <>
            <p className="text-sm leading-relaxed text-gray-200">{item.data.sample_answer}</p>
            {item.data.key_phrases.length > 0 && (
              <div className="mt-3 pt-3 border-t border-white/5">
                <p className="text-xs text-gray-500 mb-2">Key phrases:</p>
                <div className="flex flex-wrap gap-1.5">
                  {item.data.key_phrases.map((p, i) => (
                    <span
                      key={i}
                      className="px-2 py-0.5 rounded-full text-xs bg-teal-500/10 text-teal-400 border border-teal-500/20"
                    >
                      {p}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : null}
      </div>
    </div>
  )
}
