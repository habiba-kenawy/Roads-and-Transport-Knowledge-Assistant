import { Info, MessageSquare, Plus, Search } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { TabsList, TabsTrigger } from '@/components/ui/tabs'

const MAIN_PAGES = [
  { value: 'assistant', label: 'Assistant', Icon: MessageSquare },
  { value: 'inspector', label: 'Search Inspector', Icon: Search },
]

// Rendered inside <Tabs>: the pages are the tabs, so arrow keys move between them. The active page is tinted blue.
const PAGE_LINK =
  'h-10 flex-none justify-start gap-3 rounded-xl border-0 px-3 text-sm font-medium text-foreground/80 shadow-none after:hidden ' +
  'hover:bg-accent hover:text-foreground data-[state=active]:bg-accent data-[state=active]:font-semibold data-[state=active]:text-brand'
const LIST = 'h-auto w-full flex-col items-stretch gap-1 rounded-none bg-transparent p-0'

// Left column: wordmark, New conversation, the two working pages, and About at the bottom.
export function Sidebar({ onNewConversation }: { onNewConversation: () => void }) {
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

      <TabsList aria-label="Pages" className={LIST}>
        {MAIN_PAGES.map(({ value, label, Icon }) => (
          <TabsTrigger key={value} value={value} className={PAGE_LINK}>
            <Icon aria-hidden /> {label}
          </TabsTrigger>
        ))}
      </TabsList>

      <TabsList aria-label="Information" className={`${LIST} mt-auto border-t border-border pt-4`}>
        <TabsTrigger value="about" className={PAGE_LINK}>
          <Info aria-hidden /> About
        </TabsTrigger>
      </TabsList>
    </div>
  )
}
