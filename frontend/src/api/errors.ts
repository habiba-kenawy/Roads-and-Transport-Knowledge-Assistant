import axios from 'axios'

import { MAX_MESSAGE_CHARS } from '@/lib/options'
import type { ValidationIssue } from '@/types'

// What the screens show when a request fails: plain words, never a status code or a stack trace.
type ErrorKind = 'network' | 'timeout' | 'busy' | 'not_pending' | 'validation' | 'not_ready' | 'model' | 'unknown'
export interface FriendlyError {
  kind: ErrorKind
  message: string
  canRetry: boolean // true when sending the same thing again could work
}
type ApiAction = 'chat' | 'resume' | 'search'

const TOO_SLOW = 'This is taking too long. The server may still be working on it: wait a moment, then try again.'
const MAX_QUERY_CHARS = 500 // /search is stricter than /chat

function validationMessage(detail: unknown): string {
  const issue = Array.isArray(detail) ? (detail[0] as ValidationIssue | undefined) : undefined
  const field = issue?.loc.at(-1)
  if (issue && (field === 'message' || field === 'query')) {
    if (issue.type === 'string_too_short') return 'Please type something first.'
    if (issue.type === 'string_too_long')
      return `That is too long: please keep it under ${field === 'query' ? MAX_QUERY_CHARS : MAX_MESSAGE_CHARS} characters.`
  }
  return issue ? `The server did not accept that request (${issue.msg}).` : 'The server did not accept that request.'
}

// Turn anything a request can throw into a FriendlyError. The backend's answers are: 422 validation (a list of issues),
// 409 (this thread is busy, or the resume does not match a pending question), 502 (the model call failed),
// 503 (no index yet, or no model credentials), 504 (the request ran out of time), and no answer at all when the server is unreachable.
export function toFriendlyError(error: unknown, action: ApiAction): FriendlyError {
  if (!axios.isAxiosError(error)) {
    return { kind: 'unknown', message: 'Something unexpected went wrong. Please try again.', canRetry: true }
  }
  const response = error.response
  if (!response) {
    if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
      return { kind: 'timeout', message: TOO_SLOW, canRetry: true }
    }
    return { kind: 'network', message: "Cannot reach the assistant's server. Check that it is running, then try again.", canRetry: true }
  }

  const detail = (response.data as { detail?: unknown } | undefined)?.detail
  const text = typeof detail === 'string' ? detail : ''
  switch (response.status) {
    case 422:
      return { kind: 'validation', message: validationMessage(detail), canRetry: false }
    case 409:
      if (text.includes('already in progress')) {
        return {
          kind: 'busy',
          message: 'The assistant is still working on your previous message. Wait a moment, then try again.',
          canRetry: true,
        }
      }
      return {
        kind: 'not_pending',
        message:
          action === 'resume'
            ? 'This question is no longer waiting for an answer. Type your next question and it will be answered as a new one.'
            : 'This conversation is waiting for your answer to the question above. Answer it, or start a new conversation.',
        canRetry: false,
      }
    case 504:
      return { kind: 'timeout', message: TOO_SLOW, canRetry: true }
    case 502:
      return { kind: 'model', message: 'The AI model could not finish this request. Please try again.', canRetry: true }
    case 503:
      if (text.includes('index'))
        return {
          kind: 'not_ready',
          message: 'The documents have not been indexed yet. The server needs its ingestion step first.',
          canRetry: false,
        }
      if (text.includes('configured'))
        return { kind: 'not_ready', message: 'The AI model is not configured on the server.', canRetry: false }
      return { kind: 'not_ready', message: 'The service is not ready yet.', canRetry: false }
    default:
      return { kind: 'unknown', message: `Something went wrong (code ${response.status}). Please try again.`, canRetry: true }
  }
}
