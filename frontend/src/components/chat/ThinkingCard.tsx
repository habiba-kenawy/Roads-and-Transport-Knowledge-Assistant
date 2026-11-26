import { Skeleton } from '@/components/ui/skeleton'

// Shown while the graph works (several seconds): grey bars where the answer will appear, and a live-region message for screen readers.
export function ThinkingCard() {
  return (
    <output className="block rounded-2xl border border-l-4 border-border bg-card p-4 shadow-sm">
      <span className="sr-only">Searching the documents and writing an answer</span>
      <Skeleton className="h-5 w-28 rounded-full bg-border" />
      <div className="mt-4 space-y-2.5" aria-hidden>
        <Skeleton className="h-3.5 w-full bg-border" />
        <Skeleton className="h-3.5 w-11/12 bg-border" />
        <Skeleton className="h-3.5 w-3/4 bg-border" />
      </div>
      <p className="mt-4 text-xs text-muted-foreground" aria-hidden>
        Searching the documents and writing an answer...
      </p>
    </output>
  )
}
