import type { FriendlyError } from '@/api/errors'
import type { ChatResponse, Clarification } from '@/types'

// What the conversation view shows, in order.
export type Item =
  | { id: string; type: 'user'; text: string }
  | { id: string; type: 'answer'; response: ChatResponse }
  | { id: string; type: 'error'; error: FriendlyError; text: string }

// A saved conversation. threadId is the SERVER's thread, so opening it later lets the assistant remember the earlier questions.
export interface Conversation {
  id: string
  threadId: string | null
  title: string
  updatedAt: number // milliseconds since 1970
  items: Item[]
  pending: Clarification | null // the clarifying question still waiting for an answer, if any
}

// Past conversations live in this browser only (localStorage): per browser and per device, and gone if the user clears site data.
const KEY = 'tareeq.conversations.v1'
const MAX_CONVERSATIONS = 50

const isObject = (x: unknown): x is Record<string, unknown> => typeof x === 'object' && x !== null

function isItem(x: unknown): boolean {
  if (!isObject(x) || typeof x.id !== 'string') return false
  if (x.type === 'user') return typeof x.text === 'string'
  if (x.type === 'answer') return isObject(x.response) && typeof x.response.status === 'string' && typeof x.response.thread_id === 'string' && Array.isArray(x.response.citations)
  return false // error items are never saved
}

function isConversation(x: unknown): x is Conversation {
  return (
    isObject(x) &&
    typeof x.id === 'string' &&
    typeof x.title === 'string' &&
    typeof x.updatedAt === 'number' &&
    (x.threadId === null || typeof x.threadId === 'string') &&
    Array.isArray(x.items) &&
    x.items.length > 0 &&
    x.items.every(isItem) &&
    (x.pending === null || (isObject(x.pending) && typeof x.pending.interrupt_id === 'string' && typeof x.pending.question === 'string'))
  )
}

// Read what is stored. Anything unreadable, damaged or from another format is ignored: history just starts empty, nothing crashes.
export function loadConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(KEY)
    const parsed: unknown = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.filter(isConversation).sort((a, b) => b.updatedAt - a.updatedAt).slice(0, MAX_CONVERSATIONS) : []
  } catch {
    return []
  }
}

// Storage can be full or blocked (private windows): then history is simply not saved.
export function saveConversations(list: Conversation[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(list.slice(0, MAX_CONVERSATIONS)))
  } catch {
    /* nothing to do */
  }
}

// Only settled turns are saved: no error cards, and no question that never got its answer.
export function storable(items: Item[]): Item[] {
  const kept = items.filter((item) => item.type !== 'error')
  return kept.at(-1)?.type === 'user' ? kept.slice(0, -1) : kept
}

export function titleOf(items: Item[]): string {
  const first = items.find((item) => item.type === 'user')
  const text = first?.type === 'user' ? first.text.replace(/\s+/g, ' ').trim() : 'Conversation'
  return text.length > 60 ? `${text.slice(0, 57)}...` : text
}

export type DayGroup = 'Today' | 'Yesterday' | 'Previous 7 days' | 'Older'
export const DAY_GROUPS: DayGroup[] = ['Today', 'Yesterday', 'Previous 7 days', 'Older']

export function dayGroup(updatedAt: number, now = new Date()): DayGroup {
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const day = 86_400_000
  if (updatedAt >= startOfToday) return 'Today'
  if (updatedAt >= startOfToday - day) return 'Yesterday'
  if (updatedAt >= startOfToday - 7 * day) return 'Previous 7 days'
  return 'Older'
}
