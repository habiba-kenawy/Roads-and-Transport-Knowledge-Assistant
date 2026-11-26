import { useEffect, useRef, useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { MAX_MESSAGE_CHARS } from '@/lib/options'

// The answer box inside a clarifying question's card: the question and the place to answer it are together.
// It sends through the same path as the main box (the chat sends it to /chat/resume while a question is pending).
export function ClarificationReply({ onReply, disabled }: { onReply: (text: string) => void; disabled: boolean }) {
  const [text, setText] = useState('')
  const input = useRef<HTMLInputElement>(null)

  // A new question appeared: put the cursor in its answer box so the user can just type.
  useEffect(() => {
    input.current?.focus()
  }, [])

  function submit(event: FormEvent) {
    event.preventDefault()
    const answer = text.trim()
    if (!answer || disabled) return
    onReply(answer)
    setText('')
  }

  return (
    <form onSubmit={submit} className="mt-3 flex gap-2">
      <label className="sr-only" htmlFor="clarification-answer">
        Your answer to the question above
      </label>
      <Input
        ref={input}
        id="clarification-answer"
        value={text}
        onChange={(e) => setText(e.target.value)}
        maxLength={MAX_MESSAGE_CHARS}
        placeholder="Type your answer..."
        autoComplete="off"
        disabled={disabled}
      />
      <Button type="submit" disabled={disabled || text.trim().length === 0}>
        Answer
      </Button>
    </form>
  )
}
