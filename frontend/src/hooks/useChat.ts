import axios from 'axios'
import { useReducer, useRef } from 'react'

import { resumeChat, sendChat } from '@/api/client'
import { toFriendlyError, type FriendlyError } from '@/api/errors'
import type { Controls } from '@/lib/options'
import type { ChatResponse, Clarification } from '@/types'

// What the conversation view shows, in order.
export type Item =
  | { id: string; type: 'user'; text: string }
  | { id: string; type: 'answer'; response: ChatResponse }
  | { id: string; type: 'error'; error: FriendlyError; text: string }

interface State {
  items: Item[]
  threadId: string | null // kept only in memory: a page refresh starts a new conversation (see the note in useChat)
  pending: Clarification | null // set while the server waits for the user's answer to a clarifying question
  busy: boolean // true from sending until the answer arrives: the UI blocks a second send, like the server's one-run-per-thread rule
}

type Action =
  | { type: 'sent'; text: string }
  | { type: 'received'; response: ChatResponse }
  | { type: 'failed'; error: FriendlyError; text: string }
  | { type: 'retrying' }
  | { type: 'reset' }

const newId = () => crypto.randomUUID()
const initial: State = { items: [], threadId: null, pending: null, busy: false }

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'sent':
      return { ...state, busy: true, items: [...state.items, { id: newId(), type: 'user', text: action.text }] }
    case 'received':
      return {
        ...state,
        busy: false,
        threadId: action.response.thread_id,
        pending: action.response.status === 'needs_clarification' ? action.response.clarification : null,
        items: [...state.items, { id: newId(), type: 'answer', response: action.response }],
      }
    case 'failed':
      return { ...state, busy: false, items: [...state.items, { id: newId(), type: 'error', error: action.error, text: action.text }] }
    case 'retrying':
      return { ...state, busy: true, items: state.items.filter((item) => item.type !== 'error') }
    case 'reset':
      return initial
  }
}

// The conversation: sends messages, shows the server's replies, and answers clarifying questions.
// thread_id is kept in component state, not in browser storage. Trade-off: a refresh or "New conversation" starts a fresh thread
// (the old one stays on the server, unreachable from here), but there is nothing stale to restore and nothing to clean up.
export function useChat(controls: Controls) {
  const [state, dispatch] = useReducer(reducer, initial)
  const inFlight = useRef<AbortController | null>(null)

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
      dispatch({ type: 'received', response })
    } catch (error) {
      if (axios.isCancel(error)) return // "New conversation" cancelled it: nothing to show
      dispatch({ type: 'failed', error: toFriendlyError(error, action), text })
    }
  }

  return {
    items: state.items,
    busy: state.busy,
    waitingForClarification: state.pending !== null,
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
      inFlight.current?.abort()
      dispatch({ type: 'reset' })
    },
  }
}
