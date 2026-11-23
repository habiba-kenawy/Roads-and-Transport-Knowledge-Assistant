import { TriangleAlert } from 'lucide-react'

import type { FriendlyError } from '@/api/errors'
import { Button } from '@/components/ui/button'

// A failed request, in plain words, with "Try again" when sending the same message again could work.
export function ErrorCard({ error, onRetry, disabled }: { error: FriendlyError; onRetry: () => void; disabled: boolean }) {
  return (
    <div role="alert" className="rounded-2xl border border-l-4 border-border border-l-accent-red bg-card p-4 shadow-sm">
      <p className="flex items-start gap-2 text-sm text-card-foreground">
        <TriangleAlert className="mt-0.5 size-4 shrink-0 text-accent-red" aria-hidden />
        <span>{error.message}</span>
      </p>
      {error.canRetry && (
        <Button variant="outline" size="sm" className="mt-3" onClick={onRetry} disabled={disabled}>
          Try again
        </Button>
      )}
    </div>
  )
}
