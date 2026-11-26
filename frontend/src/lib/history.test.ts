import { afterEach, describe, expect, it, vi } from 'vitest'

import { STORAGE_KEY, dayGroup, loadConversations, saveConversations, storable, titleOf, type Conversation, type Item } from '@/lib/history'
import type { ChatResponse } from '@/types'

const response = (status: ChatResponse['status'] = 'answered'): ChatResponse => ({
  thread_id: 't1',
  status,
  answer: 'An answer [1].',
  citations: [],
  clarification: null,
  request_id: 'r1',
})

const conversation = (id: string, updatedAt: number): Conversation => ({
  id,
  threadId: 't1',
  title: `Conversation ${id}`,
  updatedAt,
  pending: null,
  items: [
    { id: `${id}-u`, type: 'user', text: 'A question' },
    { id: `${id}-a`, type: 'answer', response: response() },
  ],
})

// An in-memory stand-in for the browser's localStorage.
function stubStorage(initial?: string) {
  const store = new Map<string, string>()
  if (initial !== undefined) store.set(STORAGE_KEY, initial)
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => void store.set(key, value),
  })
  return store
}

afterEach(() => vi.unstubAllGlobals())

describe('loadConversations', () => {
  it('returns saved conversations, newest first', () => {
    stubStorage()
    saveConversations([conversation('old', 1000), conversation('new', 2000)])
    expect(loadConversations().map((c) => c.id)).toEqual(['new', 'old'])
  })

  it.each([
    ['text that is not JSON', 'this is { not json'],
    ['JSON of the wrong shape', '{"a":1}'],
    ['entries missing their fields', '[{"id":"x"},{"title":3}]'],
  ])('starts empty for %s, without throwing', (_name, raw) => {
    stubStorage(raw)
    expect(loadConversations()).toEqual([])
  })

  it('keeps a valid conversation next to a broken one', () => {
    stubStorage(JSON.stringify([conversation('ok', 1), { id: 'bad', title: 5 }]))
    expect(loadConversations().map((c) => c.id)).toEqual(['ok'])
  })

  it('keeps only the 50 newest', () => {
    stubStorage()
    saveConversations(Array.from({ length: 60 }, (_, i) => conversation(`c${i}`, i)))
    const loaded = loadConversations()
    expect(loaded).toHaveLength(50)
    expect(loaded[0].id).toBe('c59')
  })

  it('works when there is no storage at all', () => {
    vi.stubGlobal('localStorage', {
      getItem: () => {
        throw new Error('blocked')
      },
    })
    expect(loadConversations()).toEqual([])
  })
})

describe('saveConversations', () => {
  it('does not throw when the storage is full or blocked', () => {
    vi.stubGlobal('localStorage', {
      setItem: () => {
        throw new Error('quota')
      },
    })
    expect(() => saveConversations([conversation('a', 1)])).not.toThrow()
  })
})

describe('storable', () => {
  const user = (id: string): Item => ({ id, type: 'user', text: 'q' })
  const answer: Item = { id: 'a', type: 'answer', response: response() }
  const error: Item = { id: 'e', type: 'error', text: 'q', error: { kind: 'network', message: 'down', canRetry: true } }

  it('drops error cards and a question that never got its answer', () => {
    expect(storable([user('u1'), answer, user('u2'), error]).map((i) => i.id)).toEqual(['u1', 'a'])
  })

  it('keeps a finished exchange as it is', () => {
    expect(storable([user('u1'), answer]).map((i) => i.id)).toEqual(['u1', 'a'])
  })
})

describe('titleOf', () => {
  it('uses the first question with its spacing tidied', () => {
    expect(titleOf([{ id: 'u', type: 'user', text: '  What   is\nthe fee? ' }])).toBe('What is the fee?')
  })

  it('shortens a long question to 60 characters', () => {
    const title = titleOf([{ id: 'u', type: 'user', text: 'x'.repeat(100) }])
    expect(title).toHaveLength(60)
    expect(title.endsWith('...')).toBe(true)
  })

  it('has a fallback title', () => {
    expect(titleOf([])).toBe('Conversation')
  })
})

describe('dayGroup', () => {
  const now = new Date(2026, 10, 26, 15, 0) // 26 November 2026, 3 pm
  const at = (daysAgo: number, hour = 12) => new Date(2026, 10, 26 - daysAgo, hour).getTime()

  it('groups by calendar day', () => {
    expect(dayGroup(at(0, 0), now)).toBe('Today')
    expect(dayGroup(at(1, 23), now)).toBe('Yesterday')
    expect(dayGroup(at(1, 0), now)).toBe('Yesterday')
    expect(dayGroup(at(3), now)).toBe('Previous 7 days')
    expect(dayGroup(at(7, 0), now)).toBe('Previous 7 days')
    expect(dayGroup(at(8), now)).toBe('Older')
  })
})
