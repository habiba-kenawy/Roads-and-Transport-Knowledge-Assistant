import { Ban, CircleCheck, MessageCircleQuestion, SearchX, type LucideIcon } from 'lucide-react'

import { ClarificationReply } from '@/components/chat/ClarificationReply'
import { Badge } from '@/components/ui/badge'
import { splitMarkers } from '@/lib/citations'
import type { ChatResponse, ChatStatus } from '@/types'

// One look per outcome: a coloured left edge and a badge, so the four results are told apart at a glance.
const LOOK: Record<ChatStatus, { label: string; Icon: LucideIcon; badge: string; edge: string }> = {
  answered: { label: 'Answered', Icon: CircleCheck, badge: 'bg-accent text-brand', edge: 'border-l-brand' },
  needs_clarification: { label: 'Needs clarification', Icon: MessageCircleQuestion, badge: 'bg-ink text-white', edge: 'border-l-ink' },
  insufficient_evidence: {
    label: 'Not enough evidence',
    Icon: SearchX,
    badge: 'bg-accent-red/10 text-accent-red',
    edge: 'border-l-accent-red',
  },
  out_of_scope: { label: 'Out of scope', Icon: Ban, badge: 'bg-muted text-foreground border-border', edge: 'border-l-muted-foreground' },
}

const MARKER =
  'ml-0.5 rounded bg-accent px-1 text-xs font-semibold text-brand hover:bg-brand hover:text-white focus-visible:ring-2 focus-visible:ring-brand'

interface Props {
  response: ChatResponse
  onOpenSource: (n: number) => void // open the drawer for source n
  waiting: boolean // this is the question the server is waiting on: show the answer box
  onReply: (text: string) => void
  busy: boolean
}

// The assistant's reply. The text is shown exactly as the server wrote it (it ends with the "not legal advice" sentence and
// any status note), as plain text with its line breaks, never as HTML. The [n] markers in it are made clickable.
export function AnswerCard({ response, onOpenSource, waiting, onReply, busy }: Props) {
  const { label, Icon, badge, edge } = LOOK[response.status]
  const text = (response.status === 'needs_clarification' ? response.clarification?.question : response.answer) ?? ''
  const parts = splitMarkers(text, response.citations.length)
  return (
    <article className={`rounded-2xl border border-l-4 border-border bg-card p-4 shadow-sm ${edge}`}>
      <Badge className={badge}>
        <Icon aria-hidden /> {label}
      </Badge>
      <p className="mt-3 text-sm leading-relaxed whitespace-pre-line text-card-foreground">
        {parts.map((part, i) =>
          part.kind === 'text' ? (
            part.text
          ) : (
            <button
              key={i}
              type="button"
              className={MARKER}
              onClick={() => onOpenSource(part.n)}
              aria-label={`Open source ${part.n}: ${response.citations[part.n - 1].title}`}
            >
              [{part.n}]
            </button>
          ),
        )}
      </p>
      {response.status === 'needs_clarification' && waiting && <ClarificationReply onReply={onReply} disabled={busy} />}
      {response.status === 'needs_clarification' && !waiting && (
        <p className="mt-2 text-xs text-muted-foreground">This question was not answered. Ask a new question to continue.</p>
      )}

      {response.citations.length > 0 && (
        <div className="mt-4 border-t border-border pt-3">
          <h3 className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">Sources</h3>
          <ol className="mt-2 space-y-1.5 text-sm">
            {response.citations.map((c, i) => (
              <li key={c.chunk_id} className="flex gap-2">
                <span className="font-semibold text-brand">[{i + 1}]</span>
                <button type="button" onClick={() => onOpenSource(i + 1)} className="text-left text-brand underline underline-offset-2">
                  {c.title}, {c.locator}
                </button>
              </li>
            ))}
          </ol>
        </div>
      )}
    </article>
  )
}
