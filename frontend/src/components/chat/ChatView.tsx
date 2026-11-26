import { useEffect, useRef, useState } from 'react'

import { AnswerCard } from '@/components/chat/AnswerCard'
import { ErrorCard } from '@/components/chat/ErrorCard'
import { SourceDrawer } from '@/components/chat/SourceDrawer'
import { ThinkingCard } from '@/components/chat/ThinkingCard'
import { UserBubble } from '@/components/chat/UserBubble'
import type { Item } from '@/lib/history'
import type { ChatResponse } from '@/types'

interface Props {
  items: Item[]
  busy: boolean
  waiting: boolean // the server is waiting for the answer to the newest clarifying question
  onRetry: () => void
  onReply: (text: string) => void
}

// The conversation so far: messages and replies in order, the loading card while a reply is on its way, and it scrolls to the newest.
// Remounted for each conversation (the parent gives it a key), so an open source drawer never carries over.
export function ChatView({ items, busy, waiting, onRetry, onReply }: Props) {
  const end = useRef<HTMLDivElement>(null)
  const [source, setSource] = useState<{ response: ChatResponse; n: number } | null>(null)
  const opener = useRef<HTMLElement | null>(null) // the marker or list entry that opened the drawer, to give focus back when it closes
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [items.length, busy])

  const lastAnswerId = [...items].reverse().find((item) => item.type === 'answer')?.id

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-6">
      <h1 className="sr-only">Conversation</h1>
      {items.map((item) =>
        item.type === 'user' ? (
          <UserBubble key={item.id} text={item.text} />
        ) : item.type === 'answer' ? (
          <AnswerCard
            key={item.id}
            response={item.response}
            onOpenSource={(n) => {
              opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
              setSource({ response: item.response, n })
            }}
            waiting={waiting && item.id === lastAnswerId}
            onReply={onReply}
            busy={busy}
          />
        ) : (
          <ErrorCard key={item.id} error={item.error} onRetry={onRetry} disabled={busy} />
        ),
      )}
      {busy && <ThinkingCard />}
      <div ref={end} />
      <SourceDrawer response={source?.response ?? null} n={source?.n ?? null} onClose={() => setSource(null)} returnFocusTo={opener} />
    </div>
  )
}
