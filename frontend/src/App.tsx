import { Menu } from 'lucide-react'
import { useRef, useState } from 'react'
import { toast } from 'sonner'

import { AboutPage } from '@/components/AboutPage'
import { Composer } from '@/components/Composer'
import { EmptyState } from '@/components/EmptyState'
import { Panel } from '@/components/Panel'
import { Sidebar } from '@/components/Sidebar'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetTitle } from '@/components/ui/sheet'
import { Tabs } from '@/components/ui/tabs'
import { Toaster } from '@/components/ui/sonner'
import { DEFAULT_CONTROLS, type Controls } from '@/lib/options'

type View = 'assistant' | 'inspector' | 'about'

// Chunk 2: the page frame only. The question box, filters and pages work locally; nothing is sent to the API yet.
export default function App() {
  const [view, setView] = useState<View>('assistant')
  const [question, setQuestion] = useState('')
  const [controls, setControls] = useState<Controls>(DEFAULT_CONTROLS)
  const [menuOpen, setMenuOpen] = useState(false)
  const composerBox = useRef<HTMLDivElement>(null)

  function go(next: View) {
    setView(next)
    setMenuOpen(false)
  }

  const sidebar = (
    <Sidebar
      onNewConversation={() => {
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
        onSubmit={() => toast.info('Not connected yet: the API calls arrive in the next chunk.')}
      />
    </div>
  )

  function pickExample(text: string) {
    setQuestion(text)
    composerBox.current?.querySelector('textarea')?.focus()
  }

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

        <main id="main" className="flex-1 overflow-y-auto pt-12 lg:pt-0">
          {view === 'assistant' && <EmptyState composer={composer} onPick={pickExample} />}
          {view === 'inspector' && (
            <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-6">
              {composer}
              <Panel title="Search results">
                <p className="text-sm text-muted-foreground">Search above to see the ranked passages, the ranking stage and the score each one carries.</p>
              </Panel>
            </div>
          )}
          {view === 'about' && (
            <div className="mx-auto w-full max-w-5xl px-4 py-6 lg:px-6">
              <AboutPage />
            </div>
          )}
        </main>
      </div>
      <Toaster position="top-right" />
    </Tabs>
  )
}
