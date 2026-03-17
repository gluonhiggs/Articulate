import { useState } from 'react'
import { fetchImprovedVersion } from '../../api/client'
import type { ImproveResponse } from '../../types'

export function ImproveSection({ attemptId }: { attemptId: number }) {
  const [result, setResult] = useState<ImproveResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function handleImprove() {
    setLoading(true)
    setError(null)
    fetchImprovedVersion(attemptId)
      .then((res) => setResult(res))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Failed to generate improvement'))
      .finally(() => setLoading(false))
  }

  if (result) {
    return (
      <div className="glow-improve rounded-xl p-4 mt-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-medium opacity-80">
            Band {result.target_band.toFixed(1)} version
          </span>
        </div>
        <p className="text-sm leading-relaxed text-gray-100">{result.improved_text}</p>
        {result.explanation && (
          <p className="text-xs text-gray-300/70 mt-2 italic">{result.explanation}</p>
        )}
      </div>
    )
  }

  return (
    <div className="mt-4">
      <button
        onClick={handleImprove}
        disabled={loading}
        className="glow-improve rounded-xl px-4 py-3 text-sm font-medium flex items-center gap-2 hover:brightness-110 transition-all disabled:opacity-50 w-full justify-center"
      >
        {loading ? (
          <>
            <div className="animate-spin h-3 w-3 border-2 border-white border-t-transparent rounded-full" />
            <span>Generating...</span>
          </>
        ) : (
          <span>Improve your response</span>
        )}
      </button>
      {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
    </div>
  )
}
