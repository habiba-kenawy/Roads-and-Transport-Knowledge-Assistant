import { Menu } from 'lucide-react'
import { useRef, useState } from 'react'
import { toast } from 'sonner'

import { AboutPage } from '@/components/AboutPage'
import { ChatView } from '@/components/ChatView'
import { Composer } from '@/components/Composer'
import { EmptyState } from '@/components/EmptyState'
import { Panel } from '@/components/Panel'
import { Sidebar } from '@/components/Sidebar'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetTitle } from '@/components/ui/sheet'
import { Tabs } from '@/components/ui/tabs'
import { Toaster } from '@/components/ui/sonner'
import { useChat } from '@/hooks/useChat'
import { DEFAULT_CONTROLS, type Controls } from '@/lib/options'

type View = 'assistant' | 'inspector' | 'about'

// Chunk 3: the Assistant talks to the API. The Search Inspector is wired up in the next chunk.
export default function App() {
  const [view, setView] = useState<View>('assistant')
  const [question, setQuestion] = useState('')
  const [controls, setControls] = useState<Controls>(DEFAULT_CONTROLS)
  const [menuOpen, setMenuOpen] = useState(false)
  const composerBox = useRef<HTMLDivElement>(null)
  const chat = useChat(controls)

  function go(next: View) {
    setView(next)
    setMenuOpen(false)
  }

  function submit() {
    const text = question.trim()
    if (view === 'assistant') {
      chat.send(text)
      setQuestion('')
    } else {
      toast.info('The Search Inspector is built in the next chunk.')
    }
  }

  const sidebar = (
    <Sidebar
      onNewConversation={() => {
        chat.reset()
        setQuestion('')
        go('assistant')
      }}
    />
  )

  const composer = (
    <div ref={composerBox} className="w-full">
      <Composer
        question={question}
        onQuestionChange={setQuestion}
        controls={controls}
        onControlsChange={setControls}
        submitLabel={view === 'assistant' ? 'Ask' : 'Search'}
        busy={view === 'assistant' && chat.busy}
        placeholder={
          view === 'assistant' && chat.waitingForClarification ? 'Type your answer to the question above...' : 'Ask about Roads and Transport legislation...'
        }
        onSubmit={submit}
      />
    </div>
  )

  function pickExample(text: string) {
    setQuestion(text)
    composerBox.current?.querySelector('textarea')?.focus()
  }

  const conversationStarted = chat.items.length > 0 || chat.busy

  return (
    <Tabs value={view} onValueChange={(v) => go(v as View)} orientation="vertical" className="h-dvh gap-4 p-3 lg:p-4">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:bg-white focus:px-3 focus:py-2 focus:text-ink"
      >
        Skip to content
      </a>

      <aside className="hidden w-64 shrink-0 overflow-y-auto rounded-2xl bg-card shadow-md lg:block">{sidebar}</aside>

      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent side="left" className="w-72 p-0">
          <SheetTitle className="sr-only">Menu</SheetTitle>
          <SheetDescription className="sr-only">Pages</SheetDescription>
          {sidebar}
        </SheetContent>
      </Sheet>

      <div className="relative flex min-w-0 flex-1 flex-col rounded-2xl bg-card shadow-md">
        {/* Small screens only: the sidebar is hidden, so a floating button opens it as a drawer */}
        <Button variant="ghost" size="icon" className="absolute top-2 left-2 z-10 lg:hidden" onClick={() => setMenuOpen(true)} aria-label="Open menu">
          <Menu aria-hidden />
        </Button>

        <main id="main" className="flex min-h-0 flex-1 flex-col pt-12 lg:pt-0">
          {view === 'assistant' && !conversationStarted && (
            <div className="flex-1 overflow-y-auto">
              <EmptyState composer={composer} onPick={pickExample} />
            </div>
          )}
          {view === 'assistant' && conversationStarted && (
            <>
              <div className="flex-1 overflow-y-auto">
                <ChatView items={chat.items} busy={chat.busy} onRetry={chat.retry} />
              </div>
              <div className="shrink-0 border-t border-border bg-card px-4 py-3">
                <div className="mx-auto w-full max-w-3xl">{composer}</div>
              </div>
            </>
          )}
          {view === 'inspector' && (
            <div className="flex-1 overflow-y-auto">
              <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-6">
                {composer}
                <Panel title="Search results">
                  <p className="text-sm text-muted-foreground">Search above to see the ranked passages, the ranking stage and the score each one carries.</p>
                </Panel>
              </div>
            </div>
          )}
          {view === 'about' && (
            <div className="flex-1 overflow-y-auto">
              <div className="mx-auto w-full max-w-5xl px-4 py-6 lg:px-6">
                <AboutPage />
              </div>
            </div>
          )}
        </main>
      </div>
      <Toaster position="top-right" />
    </Tabs>
  )
}
