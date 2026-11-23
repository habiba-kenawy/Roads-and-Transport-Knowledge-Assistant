import { Ban, CircleCheck, MessageCircleQuestion, SearchX, type LucideIcon } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import type { ChatResponse, ChatStatus } from '@/types'

// One look per outcome: a coloured left edge and a badge, so the four results are told apart at a glance.
const LOOK: Record<ChatStatus, { label: string; Icon: LucideIcon; badge: string; edge: string }> = {
  answered: { label: 'Answered', Icon: CircleCheck, badge: 'bg-accent text-brand', edge: 'border-l-brand' },
  needs_clarification: { label: 'Needs clarification', Icon: MessageCircleQuestion, badge: 'bg-ink text-white', edge: 'border-l-ink' },
  insufficient_evidence: { label: 'Not enough evidence', Icon: SearchX, badge: 'bg-accent-red/10 text-accent-red', edge: 'border-l-accent-red' },
  out_of_scope: { label: 'Out of scope', Icon: Ban, badge: 'bg-muted text-foreground border-border', edge: 'border-l-muted-foreground' },
}

// Only link to https addresses (the portal's pages); anything else is shown as plain text.
const safeHref = (url: string) => (url.startsWith('https://') ? url : undefined)

// The assistant's reply. The text is shown exactly as the server wrote it (it ends with the "not legal advice" sentence and
// any status note), as plain text with its line breaks, never as HTML.
export function AnswerCard({ response }: { response: ChatResponse }) {
  const { label, Icon, badge, edge } = LOOK[response.status]
  const text = response.status === 'needs_clarification' ? response.clarification?.question : response.answer
  return (
    <article className={`rounded-2xl border border-l-4 border-border bg-card p-4 shadow-sm ${edge}`}>
      <Badge className={badge}>
        <Icon aria-hidden /> {label}
      </Badge>
      <p className="mt-3 text-sm leading-relaxed whitespace-pre-line text-card-foreground">{text}</p>
      {response.status === 'needs_clarification' && <p className="mt-2 text-xs text-muted-foreground">Type your answer in the box below.</p>}

      {response.citations.length > 0 && (
        <div className="mt-4 border-t border-border pt-3">
          <h3 className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">Sources</h3>
          <ol className="mt-2 space-y-1.5 text-sm">
            {response.citations.map((c, i) => {
              const href = safeHref(c.source_url)
              return (
                <li key={c.chunk_id} className="flex gap-2">
                  <span className="font-semibold text-brand">[{i + 1}]</span>
                  <span>
                    {href ? (
                      <a href={href} target="_blank" rel="noopener noreferrer" className="text-brand underline underline-offset-2">
                        {c.title}
                      </a>
                    ) : (
                      c.title
                    )}
                    , {c.locator}
                  </span>
                </li>
              )
            })}
          </ol>
        </div>
      )}
    </article>
  )
}
