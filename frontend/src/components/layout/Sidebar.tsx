import { Info, MessageSquare, Plus, Search, type LucideIcon } from 'lucide-react'

import { HistoryList } from '@/components/layout/HistoryList'
import { Button } from '@/components/ui/button'
import type { Conversation } from '@/lib/history'

export type View = 'assistant' | 'inspector' | 'about'

interface Props {
  view: View
  onNavigate: (view: View) => void
  onNewConversation: () => void
  conversations: Conversation[]
  activeId: string
  onOpenConversation: (id: string) => void
  onDeleteConversation: (id: string) => void
}

const WORKING_PAGES: { view: View; label: string; Icon: LucideIcon }[] = [
  { view: 'assistant', label: 'Assistant', Icon: MessageSquare },
  { view: 'inspector', label: 'Search Inspector', Icon: Search },
]

const PAGE_LINK =
  'h-10 w-full justify-start gap-3 rounded-xl px-3 text-sm font-medium text-foreground/80 hover:bg-accent hover:text-foreground ' +
  'aria-[current=page]:bg-accent aria-[current=page]:font-semibold aria-[current=page]:text-brand'

// Left column: wordmark, New conversation, the two working pages, past conversations (scrolls), and About at the bottom.
export function Sidebar({ view, onNavigate, onNewConversation, conversations, activeId, onOpenConversation, onDeleteConversation }: Props) {
  const pageLink = (target: View, label: string, Icon: LucideIcon) => (
    <Button
      key={target}
      variant="ghost"
      className={PAGE_LINK}
      onClick={() => onNavigate(target)}
      aria-current={view === target ? 'page' : undefined}
    >
      <Icon aria-hidden /> {label}
    </Button>
  )

  return (
    <div className="flex h-full flex-col gap-5 p-4">
      <div className="px-1 pt-1">
        <span className="text-xl font-bold tracking-[0.25em] uppercase">TAREEQ</span>
        <div className="mt-1 h-0.5 w-10 bg-accent-red" aria-hidden />
        <p className="mt-2 text-xs text-muted-foreground">Roads and Transport Knowledge Assistant</p>
      </div>

      <div data-surface="dark">
        <Button className="h-11 w-full rounded-xl bg-ink text-white hover:bg-ink/90" onClick={onNewConversation}>
          <Plus aria-hidden /> New conversation
        </Button>
      </div>

      <nav aria-label="Pages" className="flex flex-col gap-1">
        {WORKING_PAGES.map(({ view: target, label, Icon }) => pageLink(target, label, Icon))}
      </nav>

      <div className="flex min-h-0 flex-1 flex-col border-t border-border pt-4">
        <div className="min-h-0 flex-1 overflow-y-auto">
          <HistoryList conversations={conversations} activeId={activeId} onOpen={onOpenConversation} onDelete={onDeleteConversation} />
        </div>
      </div>

      <nav aria-label="Information" className="border-t border-border pt-4">
        {pageLink('about', 'About', Info)}
      </nav>
    </div>
  )
}
