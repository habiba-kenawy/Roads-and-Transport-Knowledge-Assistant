import { useEffect, useRef } from 'react'

import { AnswerCard } from '@/components/AnswerCard'
import { ErrorCard } from '@/components/ErrorCard'
import { ThinkingCard } from '@/components/ThinkingCard'
import { UserBubble } from '@/components/UserBubble'
import type { Item } from '@/lib/history'

// The conversation so far: messages and replies in order, the loading card while a reply is on its way, and it scrolls to the newest.
export function ChatView({ items, busy, onRetry }: { items: Item[]; busy: boolean; onRetry: () => void }) {
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [items.length, busy])

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-6">
      {items.map((item) =>
        item.type === 'user' ? (
          <UserBubble key={item.id} text={item.text} />
        ) : item.type === 'answer' ? (
          <AnswerCard key={item.id} response={item.response} />
        ) : (
          <ErrorCard key={item.id} error={item.error} onRetry={onRetry} disabled={busy} />
        ),
      )}
      {busy && <ThinkingCard />}
      <div ref={end} />
    </div>
  )
}
