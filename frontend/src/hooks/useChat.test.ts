import { describe, expect, it } from 'vitest'

import type { FriendlyError } from '@/api/errors'
import { chatReducer, freshChat, type State } from '@/hooks/useChat'
import type { ChatResponse } from '@/types'

const answered: ChatResponse = {
  thread_id: 't1',
  status: 'answered',
  answer: 'It is AED 75 [1].',
  citations: [],
  clarification: null,
  request_id: 'r1',
}
const asking: ChatResponse = {
  thread_id: 't1',
  status: 'needs_clarification',
  answer: null,
  citations: [],
  clarification: { interrupt_id: 'i1', question: 'Which fee?' },
  request_id: 'r2',
}
const failure = (kind: FriendlyError['kind']): FriendlyError => ({ kind, message: 'failed', canRetry: kind !== 'not_pending' })

const start = (): State => freshChat([])
const ask = (state: State, text: string) => chatReducer(state, { type: 'sent', text })
const reply = (state: State, response: ChatResponse, at = 1000) => chatReducer(state, { type: 'received', response, at })

describe('chatReducer', () => {
  it('blocks a second send while a request is running and adds the question to the conversation', () => {
    const state = ask(start(), 'What is the fee?')
    expect(state.busy).toBe(true)
    expect(state.items).toMatchObject([{ type: 'user', text: 'What is the fee?' }])
  })

  it('saves the conversation with its server thread once the answer arrives', () => {
    const state = reply(ask(start(), 'What is the fee?'), answered)
    expect(state.busy).toBe(false)
    expect(state.threadId).toBe('t1')
    expect(state.conversations).toHaveLength(1)
    expect(state.conversations[0]).toMatchObject({ id: state.id, threadId: 't1', title: 'What is the fee?', pending: null })
  })

  it('remembers the clarifying question so the next message resumes it', () => {
    const state = reply(ask(start(), 'What is the fine?'), asking)
    expect(state.pending).toEqual({ interrupt_id: 'i1', question: 'Which fee?' })
    expect(state.conversations[0].pending).toEqual(state.pending)
  })

  it('stops waiting for an answer when the server refuses the resume, in memory and in the saved copy', () => {
    const waiting = reply(ask(start(), 'What is the fine?'), asking)
    const refused = chatReducer(ask(waiting, 'the airport fee'), { type: 'failed', error: failure('not_pending'), text: 'the airport fee' })
    expect(refused.pending).toBeNull()
    expect(refused.conversations[0].pending).toBeNull()
    expect(refused.items.at(-1)).toMatchObject({ type: 'error' })
  })

  it('keeps waiting after an error that is not a refused resume', () => {
    const waiting = reply(ask(start(), 'What is the fine?'), asking)
    const failed = chatReducer(ask(waiting, 'the airport fee'), { type: 'failed', error: failure('network'), text: 'the airport fee' })
    expect(failed.pending).not.toBeNull()
    expect(failed.conversations[0].pending).not.toBeNull()
  })

  it('never saves an error card, and retrying removes it', () => {
    const failed = chatReducer(ask(start(), 'q'), { type: 'failed', error: failure('network'), text: 'q' })
    expect(failed.busy).toBe(false)
    const retrying = chatReducer(failed, { type: 'retrying' })
    expect(retrying.busy).toBe(true)
    expect(retrying.items.some((item) => item.type === 'error')).toBe(false)
  })

  it('moves the most recently used conversation to the top', () => {
    const first = reply(ask(start(), 'first question'), answered, 1000)
    const second = reply(ask(chatReducer(first, { type: 'reset' }), 'second question'), { ...answered, thread_id: 't2' }, 2000)
    expect(second.conversations.map((c) => c.title)).toEqual(['second question', 'first question'])

    const reopened = chatReducer(second, { type: 'load', conversation: second.conversations[1] })
    const continued = reply(ask(reopened, 'one more'), answered, 3000)
    expect(continued.conversations[0].title).toBe('first question')
    expect(continued.conversations).toHaveLength(2)
  })

  it('starts a blank conversation on reset but keeps the saved ones', () => {
    const saved = reply(ask(start(), 'q'), answered)
    const blank = chatReducer(saved, { type: 'reset' })
    expect(blank).toMatchObject({ items: [], threadId: null, pending: null, busy: false })
    expect(blank.id).not.toBe(saved.id)
    expect(blank.conversations).toHaveLength(1)
  })

  it('removes a conversation and brings it back on undo', () => {
    const saved = reply(ask(start(), 'q'), answered)
    const removed = chatReducer(saved, { type: 'remove', id: saved.id })
    expect(removed.conversations).toHaveLength(0)
    const restored = chatReducer(removed, { type: 'restore', conversation: saved.conversations[0] })
    expect(restored.conversations).toHaveLength(1)
  })
})
