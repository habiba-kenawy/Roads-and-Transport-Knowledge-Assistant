import { AxiosError, type AxiosResponse } from 'axios'
import { describe, expect, it } from 'vitest'

import { toFriendlyError } from '@/api/errors'

// An error as axios raises it when the server answered with this status and body.
function answered(status: number, data: unknown): AxiosError {
  const response = { status, data, statusText: '', headers: {}, config: {} } as AxiosResponse
  return new AxiosError('failed', 'ERR_BAD_REQUEST', undefined, undefined, response)
}

describe('toFriendlyError', () => {
  it('says the server is unreachable when there is no answer', () => {
    const error = toFriendlyError(new AxiosError('Network Error', 'ERR_NETWORK'), 'chat')
    expect(error).toMatchObject({ kind: 'network', canRetry: true })
    expect(error.message).toMatch(/Cannot reach/)
  })

  it('reports a timeout separately, whether the page or the server gave up', () => {
    expect(toFriendlyError(new AxiosError('timeout', 'ECONNABORTED'), 'chat').kind).toBe('timeout')
    const serverGaveUp = toFriendlyError(answered(504, { detail: 'the request took longer than 60 seconds' }), 'chat')
    expect(serverGaveUp).toMatchObject({ kind: 'timeout', canRetry: true })
    expect(serverGaveUp.message).not.toMatch(/504/)
  })

  it('tells a busy thread from a question that is no longer waiting (both are 409)', () => {
    const busy = toFriendlyError(answered(409, { detail: 'a run is already in progress for thread t1' }), 'chat')
    expect(busy).toMatchObject({ kind: 'busy', canRetry: true })

    const notWaiting = toFriendlyError(answered(409, { detail: 'thread t1 is not waiting for an answer' }), 'resume')
    expect(notWaiting).toMatchObject({ kind: 'not_pending', canRetry: false })
    expect(notWaiting.message).toMatch(/no longer waiting/)
  })

  it('words an empty or over-long message in plain language, with the right limit per endpoint', () => {
    const empty = answered(422, { detail: [{ loc: ['body', 'message'], msg: 'x', type: 'string_too_short' }] })
    expect(toFriendlyError(empty, 'chat').message).toBe('Please type something first.')

    const tooLong = (field: string) => answered(422, { detail: [{ loc: ['body', field], msg: 'x', type: 'string_too_long' }] })
    expect(toFriendlyError(tooLong('message'), 'chat').message).toMatch(/2000/)
    expect(toFriendlyError(tooLong('query'), 'search').message).toMatch(/500/)
  })

  it('maps model failures and missing set-up to their own messages, never a status code', () => {
    expect(toFriendlyError(answered(502, { detail: 'model call failed' }), 'chat').kind).toBe('model')
    expect(toFriendlyError(answered(503, { detail: 'the search index is not built' }), 'chat').message).toMatch(/indexed/)
    expect(toFriendlyError(answered(503, { detail: 'chat model is not configured' }), 'chat').message).toMatch(/not configured/)
    expect(toFriendlyError(answered(500, {}), 'chat').message).not.toMatch(/Traceback/)
  })

  it('handles an error that did not come from axios', () => {
    expect(toFriendlyError(new Error('boom'), 'chat')).toMatchObject({ kind: 'unknown', canRetry: true })
  })
})
