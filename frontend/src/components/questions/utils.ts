// ── Shared helper functions for question components ──────────────────────────

export function partMaxSeconds(part: string): number {
  return part === '2' ? 120 : part === '3' ? 60 : 45
}

export function partLabel(part: string): string {
  return part === '1' ? 'Part 1' : part === '2' ? 'Part 2' : part === '3' ? 'Part 3' : 'Custom'
}

export function partRoute(part: string, id?: number): string {
  const base = part === '1' ? '/practice/part1' : part === '2' ? '/practice/part2' : part === '3' ? '/practice/part3' : '/'
  return id !== undefined ? `${base}/questions/${id}` : base
}

export function scoreColor(s: number) {
  if (s >= 7) return { ring: 'border-teal-400', text: 'text-teal-400', glow: 'glow-circle' }
  if (s >= 6) return { ring: 'border-purple-400', text: 'text-purple-400', glow: '' }
  if (s >= 5) return { ring: 'border-yellow-400', text: 'text-yellow-400', glow: '' }
  return { ring: 'border-red-400', text: 'text-red-400', glow: '' }
}

export function tagClass(s: number) {
  if (s >= 7) return 'tag-high'
  if (s >= 5) return 'tag-mid'
  return 'tag-low'
}

export function cleanWord(s: string): string {
  return s.replace(/[.,!?;:'"()\-]/g, '').toLowerCase()
}
