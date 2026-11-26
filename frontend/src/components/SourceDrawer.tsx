import { ExternalLink } from 'lucide-react'
import type { RefObject } from 'react'

import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { sentencesCiting } from '@/lib/citations'
import type { ChatResponse } from '@/types'

// Only link to https addresses (the portal's pages); anything else is not offered as a link.
const safeHref = (url: string) => (url.startsWith('https://') ? url : undefined)

// The side panel behind a [n] marker: which document and page the claim comes from, which answer sentences rely on it,
// and a link to the official page. (The chat API returns the reference, not the passage text: that is in the Search Inspector.)
export function SourceDrawer({ response, n, onClose, returnFocusTo }: { response: ChatResponse | null; n: number | null; onClose: () => void; returnFocusTo: RefObject<HTMLElement | null> }) {
  const citation = response && n ? response.citations[n - 1] : undefined
  const uses = response && n && response.answer ? sentencesCiting(response.answer, n) : []
  const href = citation ? safeHref(citation.source_url) : undefined
  return (
    <Sheet open={citation !== undefined} onOpenChange={(open) => !open && onClose()}>
      <SheetContent
        side="right"
        className="w-full gap-0 overflow-y-auto sm:max-w-md"
        onCloseAutoFocus={(event) => {
          event.preventDefault() // there is no trigger button to return to, so send focus back to the marker that opened the panel
          returnFocusTo.current?.focus()
        }}
      >
        {citation && (
          <>
            <SheetHeader className="pr-12">
              <SheetTitle>Source [{n}]</SheetTitle>
              <SheetDescription>{citation.title}</SheetDescription>
            </SheetHeader>
            <div className="space-y-5 px-4 pb-6 text-sm">
              <dl className="grid grid-cols-[6.5rem_1fr] gap-x-3 gap-y-2">
                <dt className="text-muted-foreground">Where in it</dt>
                <dd className="font-medium">{citation.locator}</dd>
                <dt className="text-muted-foreground">Document id</dt>
                <dd className="font-mono text-xs break-all">{citation.document_id}</dd>
                <dt className="text-muted-foreground">Passage id</dt>
                <dd className="font-mono text-xs break-all">{citation.chunk_id}</dd>
              </dl>

              <section aria-labelledby="used-for">
                <h3 id="used-for" className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                  Used in the answer for
                </h3>
                {uses.length > 0 ? (
                  <ul className="mt-2 space-y-2">
                    {uses.map((sentence) => (
                      <li key={sentence} className="rounded-lg bg-surface p-3 leading-relaxed">
                        {sentence}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-muted-foreground">No sentence of this answer points to this source.</p>
                )}
              </section>

              {href ? (
                <Button asChild variant="outline" className="w-full">
                  <a href={href} target="_blank" rel="noopener noreferrer">
                    <ExternalLink aria-hidden /> Open the official source
                  </a>
                </Button>
              ) : (
                <p className="text-muted-foreground">This source has no official link.</p>
              )}
              <p className="text-xs text-muted-foreground">
                The assistant keeps the reference, not the passage text. To read the passages the search finds, use the Search Inspector.
                Always check the official source: this is not legal advice and may not be current.
              </p>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}
