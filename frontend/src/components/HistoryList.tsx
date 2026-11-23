import { Trash2 } from 'lucide-react'

import { DAY_GROUPS, dayGroup, type Conversation } from '@/lib/history'

interface Props {
  conversations: Conversation[]
  activeId: string
  onOpen: (id: string) => void
  onDelete: (id: string) => void
}

// Past conversations, newest first, grouped by day. Each row opens the conversation; the bin deletes it (with Undo).
export function HistoryList({ conversations, activeId, onOpen, onDelete }: Props) {
  if (conversations.length === 0) {
    return <p className="px-1 text-xs text-muted-foreground">Your past conversations will appear here.</p>
  }
  return (
    <nav aria-label="Past conversations" className="space-y-4">
      {DAY_GROUPS.map((group) => {
        const rows = conversations.filter((c) => dayGroup(c.updatedAt) === group)
        if (rows.length === 0) return null
        return (
          <div key={group}>
            <h3 className="px-1 text-xs font-semibold tracking-wider text-muted-foreground uppercase">{group}</h3>
            <ul className="mt-1 space-y-0.5">
              {rows.map((c) => (
                <li key={c.id} className="group relative">
                  <button
                    type="button"
                    onClick={() => onOpen(c.id)}
                    aria-current={c.id === activeId ? 'true' : undefined}
                    className={`block w-full truncate rounded-lg py-2 pr-9 pl-3 text-left text-sm hover:bg-accent ${
                      c.id === activeId ? 'bg-accent font-medium text-brand' : 'text-foreground/80'
                    }`}
                  >
                    {c.title}
                  </button>
                  {/* Always visible on touch screens; on desktop it appears on hover or keyboard focus */}
                  <button
                    type="button"
                    onClick={() => onDelete(c.id)}
                    aria-label={`Delete conversation: ${c.title}`}
                    className="absolute top-1/2 right-1.5 flex size-7 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground hover:bg-card hover:text-accent-red focus-visible:opacity-100 sm:opacity-0 sm:group-focus-within:opacity-100 sm:group-hover:opacity-100"
                  >
                    <Trash2 className="size-4" aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )
      })}
    </nav>
  )
}
