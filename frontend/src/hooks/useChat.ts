import axios from 'axios'
import { useEffect, useReducer, useRef } from 'react'

import { resumeChat, sendChat } from '@/api/client'
import { toFriendlyError, type FriendlyError } from '@/api/errors'
import { loadConversations, saveConversations, storable, titleOf, type Conversation, type Item } from '@/lib/history'
import type { Controls } from '@/lib/options'
import type { ChatResponse, Clarification } from '@/types'

export interface State {
  conversations: Conversation[] // saved conversations, newest first; the open one is in here once it has an answered turn
  // the open conversation:
  id: string // our own id (the key it is saved under); the SERVER's id is threadId
  items: Item[]
  threadId: string | null // null until the server answers the first message and creates the thread
  pending: Clarification | null // set while the server waits for the user's answer to a clarifying question
  busy: boolean // true from sending until the answer arrives: the UI blocks a second send, like the server's one-run-per-thread rule
}

export type Action =
  | { type: 'sent'; text: string }
  | { type: 'received'; response: ChatResponse; at: number }
  | { type: 'failed'; error: FriendlyError; text: string }
  | { type: 'retrying' }
  | { type: 'reset' }
  | { type: 'load'; conversation: Conversation }
  | { type: 'remove'; id: string }
  | { type: 'restore'; conversation: Conversation }

const newId = () => crypto.randomUUID()
export const freshChat = (conversations: Conversation[]): State => ({
  id: newId(),
  items: [],
  threadId: null,
  pending: null,
  busy: false,
  conversations,
})
const newestFirst = (list: Conversation[]) => [...list].sort((a, b) => b.updatedAt - a.updatedAt)
const withEntry = (list: Conversation[], entry: Conversation) => newestFirst([entry, ...list.filter((c) => c.id !== entry.id)])

export function chatReducer(state: State, action: Action): State {
  switch (action.type) {
    case 'sent':
      return { ...state, busy: true, items: [...state.items, { id: newId(), type: 'user', text: action.text }] }
    case 'received': {
      const items = [...state.items, { id: newId(), type: 'answer' as const, response: action.response }]
      const pending = action.response.status === 'needs_clarification' ? action.response.clarification : null
      const saved: Conversation = {
        id: state.id,
        threadId: action.response.thread_id,
        title: titleOf(items),
        updatedAt: action.at,
        items: storable(items),
        pending,
      }
      return {
        ...state,
        busy: false,
        threadId: action.response.thread_id,
        pending,
        items,
        conversations: withEntry(state.conversations, saved),
      }
    }
    case 'failed': {
      // The server refused a resume ("not waiting for an answer"): stop treating the next message as an answer, here and in the saved copy,
      // or the conversation would try the same refused resume forever.
      const staleQuestion = action.error.kind === 'not_pending' && state.pending !== null
      return {
        ...state,
        busy: false,
        pending: staleQuestion ? null : state.pending,
        conversations: staleQuestion
          ? state.conversations.map((c) => (c.id === state.id ? { ...c, pending: null } : c))
          : state.conversations,
        items: [...state.items, { id: newId(), type: 'error', error: action.error, text: action.text }],
      }
    }
    case 'retrying':
      return { ...state, busy: true, items: state.items.filter((item) => item.type !== 'error') }
    case 'reset':
      return freshChat(state.conversations)
    case 'load': {
      const { id, items, threadId, pending } = action.conversation
      return { ...state, id, items, threadId, pending, busy: false }
    }
    case 'remove':
      return { ...state, conversations: state.conversations.filter((c) => c.id !== action.id) }
    case 'restore':
      return { ...state, conversations: withEntry(state.conversations, action.conversation) }
  }
}

// The chat: sends messages, shows the server's replies, answers clarifying questions, and keeps past conversations.
// thread_id is the server's key for a conversation's memory. It is saved WITH the conversation, so reopening a past conversation
// continues on the same server thread and the assistant still remembers the earlier questions.
export function useChat(controls: Controls) {
  const [state, dispatch] = useReducer(chatReducer, undefined, () => freshChat(loadConversations()))
  const inFlight = useRef<AbortController | null>(null)

  // The browser's storage is the one outside system this hook has to keep in step with.
  useEffect(() => saveConversations(state.conversations), [state.conversations])

  // One request. If the server is waiting for a clarification the text is the answer to it (resume), otherwise a normal message.
  async function run(text: string) {
    const controller = new AbortController()
    inFlight.current = controller
    const action = state.pending ? 'resume' : 'chat'
    try {
      const response =
        state.pending && state.threadId
          ? await resumeChat({ thread_id: state.threadId, interrupt_id: state.pending.interrupt_id, message: text }, controller.signal)
          : await sendChat(
              {
                message: text,
                thread_id: state.threadId, // null on the first message: the server creates the thread and returns its id
                search_mode: controls.mode,
                top_k: controls.topK,
                filters: { year: controls.year, doc_type: controls.docType },
              },
              controller.signal,
            )
      dispatch({ type: 'received', response, at: Date.now() })
    } catch (error) {
      if (axios.isCancel(error)) return // the user switched conversation: nothing to show
      dispatch({ type: 'failed', error: toFriendlyError(error, action), text })
    }
  }

  // Leaving a conversation cancels a request that is still running (the server finishes it, but nobody is waiting for it).
  function leave() {
    inFlight.current?.abort()
  }

  return {
    // the open conversation
    id: state.id,
    items: state.items,
    busy: state.busy,
    waitingForClarification: state.pending !== null,
    // saved conversations
    conversations: state.conversations,
    send(text: string) {
      if (state.busy) return
      dispatch({ type: 'sent', text })
      void run(text)
    },
    retry() {
      const failed = [...state.items].reverse().find((item) => item.type === 'error')
      if (state.busy || failed?.type !== 'error') return
      dispatch({ type: 'retrying' })
      void run(failed.text)
    },
    reset() {
      leave()
      dispatch({ type: 'reset' })
    },
    open(id: string) {
      const conversation = state.conversations.find((c) => c.id === id)
      if (!conversation) return
      leave()
      dispatch({ type: 'load', conversation })
    },
    // Returns the removed conversation so the caller can offer "Undo".
    remove(id: string): Conversation | undefined {
      const removed = state.conversations.find((c) => c.id === id)
      if (!removed) return undefined
      if (id === state.id) leave()
      dispatch({ type: 'remove', id })
      if (id === state.id) dispatch({ type: 'reset' }) // deleting the open conversation leaves a blank one
      return removed
    },
    restore(conversation: Conversation) {
      dispatch({ type: 'restore', conversation })
    },
  }
}
