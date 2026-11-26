import axios from 'axios'
import { useRef, useState } from 'react'

import { searchPassages } from '@/api/client'
import { toFriendlyError, type FriendlyError } from '@/api/errors'
import type { Controls } from '@/lib/options'
import type { SearchResponse } from '@/types'

export type SearchState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'done'; query: string; response: SearchResponse }
  | { status: 'error'; error: FriendlyError }

// The Search Inspector: one search at a time, shown until the next. Starting a new search cancels the one still running,
// so an old answer can never overwrite a newer one.
export function useSearch(controls: Controls) {
  const [state, setState] = useState<SearchState>({ status: 'idle' })
  const inFlight = useRef<AbortController | null>(null)

  async function run(query: string) {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    setState({ status: 'loading' })
    try {
      const response = await searchPassages(
        { query, mode: controls.mode, top_k: controls.topK, filters: { year: controls.year, doc_type: controls.docType } },
        controller.signal,
      )
      setState({ status: 'done', query, response })
    } catch (error) {
      if (axios.isCancel(error)) return // replaced by a newer search
      setState({ status: 'error', error: toFriendlyError(error, 'search') })
    }
  }

  return { state, run, busy: state.status === 'loading' }
}
