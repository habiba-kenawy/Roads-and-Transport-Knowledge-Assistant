import { TriangleAlert } from 'lucide-react'
import { useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { formatScore, scoreLabel, stageLabel } from '@/lib/scores'
import type { SearchState } from '@/hooks/useSearch'
import type { SearchHit, SearchResponse } from '@/types'

const PREVIEW_CHARS = 420

// One ranked passage: where it ranks, which document and page, what kind of score it carries, and its text (plain text, never HTML).
function Hit({ hit, fusedPosition }: { hit: SearchHit; fusedPosition: number | null }) {
  const [open, setOpen] = useState(false)
  const long = hit.text.length > PREVIEW_CHARS
  const shown = open || !long ? hit.text : `${hit.text.slice(0, PREVIEW_CHARS).trimEnd()}...`
  return (
    <li className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge className="bg-brand text-white">#{hit.rank}</Badge>
        <span className="text-sm font-semibold">{hit.title}</span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        {[hit.locator, hit.article, hit.year, hit.doc_type, hit.status].filter(Boolean).join(' · ')}
      </p>
      <p className="mt-2 text-xs">
        <span className="font-medium">{scoreLabel(hit.score_type)}:</span> {formatScore(hit.score_type, hit.score)}
        {fusedPosition !== null && <span className="text-muted-foreground"> · position {fusedPosition} before reranking</span>}
      </p>
      <p className="mt-3 text-sm leading-relaxed whitespace-pre-line">{shown}</p>
      {long && (
        <Button variant="ghost" size="sm" className="mt-1 -ml-2 text-brand" onClick={() => setOpen(!open)} aria-expanded={open}>
          {open ? 'Show less' : 'Show the whole passage'}
        </Button>
      )}
    </li>
  )
}

function Summary({ response, query }: { response: SearchResponse; query: string }) {
  return (
    <div className="text-sm">
      <p>
        <span className="font-medium">&ldquo;{query}&rdquo;</span> · {response.results.length} passage
        {response.results.length === 1 ? '' : 's'}
      </p>
      <p className="mt-1 text-xs text-muted-foreground">
        Mode: {response.mode} · Ranking stage: {stageLabel(response.ranking_stage)}
      </p>
      <p className="mt-1 text-xs text-muted-foreground">
        Scores use different scales and cannot be compared with each other. A score only orders passages inside its own list; it is not how
        sure the system is.
      </p>
    </div>
  )
}

// The Search Inspector's output: what the search found before any answer is written.
export function InspectorResults({ state }: { state: SearchState }) {
  if (state.status === 'idle') {
    return (
      <p className="text-sm text-muted-foreground">
        Search above to see the ranked passages, the ranking stage and the score each one carries.
      </p>
    )
  }
  if (state.status === 'loading') {
    return (
      <output aria-label="Searching" className="block space-y-3">
        <Skeleton className="h-24 w-full rounded-xl" />
        <Skeleton className="h-24 w-full rounded-xl" />
      </output>
    )
  }
  if (state.status === 'error') {
    return (
      <p role="alert" className="flex items-start gap-2 text-sm">
        <TriangleAlert className="mt-0.5 size-4 shrink-0 text-accent-red" aria-hidden />
        <span>{state.error.message}</span>
      </p>
    )
  }

  const { response, query } = state
  const before = response.candidates_before_rerank ?? null // chunk ids in the order they had before reranking (hybrid only)
  return (
    <div className="space-y-4">
      <Summary response={response} query={query} />
      {response.rerank_note && (
        <p role="note" className="rounded-lg bg-accent-red/10 p-3 text-xs text-accent-red">
          {response.rerank_note}
        </p>
      )}
      {response.results.length === 0 ? (
        <p className="text-sm text-muted-foreground">No passage matched. Try other words, or remove a Year or Type filter.</p>
      ) : (
        <ol className="space-y-3">
          {response.results.map((hit) => {
            const position = before ? before.indexOf(hit.chunk_id) + 1 : 0
            return <Hit key={hit.chunk_id} hit={hit} fusedPosition={position > 0 ? position : null} />
          })}
        </ol>
      )}
    </div>
  )
}
