// Asks the REAL backend the demo's questions and stores its answers in fixtures/responses.json.
// record.js replays them, so the video is repeatable, needs no model credentials, and is not at the mercy of model response times.
// Needs the API running (default http://127.0.0.1:8010) and makes real model calls (about a minute).
import { mkdirSync, writeFileSync } from 'node:fs'

import { API, QUESTIONS as Q, searchKey } from './flow.js'

const ATTEMPTS = 4

async function post(path, body) {
  const response = await fetch(API + path, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })
  if (!response.ok) throw new Error(`${path} -> HTTP ${response.status}: ${await response.text()}`)
  return response.json()
}

// The sentences of an answer, as the page shows them: "<statement> [n]." up to the first blank line.
const sentencesOf = (answer) => [...(answer ?? '').split('\n\n')[0].matchAll(/(.+?)\s*\[\d+\]\./gs)].map((m) => m[1].trim())
// A demo should not open on a sentence that starts in lower case (a known wording variation, see the README limitations).
const readsWell = (r) => r.status !== 'answered' || sentencesOf(r.answer).every((s) => /^[A-Z0-9]/.test(s))

async function ask(label, make, accept) {
  for (let attempt = 1; attempt <= ATTEMPTS; attempt++) {
    const result = await make()
    if (accept(result)) {
      console.log(`  ok   ${label}${attempt > 1 ? ` (attempt ${attempt})` : ''}: ${result.status ?? result.ranking_stage}`)
      return result
    }
    console.log(`  skip ${label} (attempt ${attempt}): not what the demo needs (${result.status ?? result.ranking_stage})`)
  }
  throw new Error(`${label}: no usable answer after ${ATTEMPTS} attempts`)
}

const chatBody = (message, thread_id = null) => ({ message, thread_id, search_mode: 'hybrid', top_k: 5, filters: { year: null, doc_type: null } })
const searchBody = (mode, filters = { year: null, doc_type: null }) => ({ query: Q.search, mode, top_k: 5, filters })

console.log(`Capturing from ${API}`)
const health = await fetch(API + '/health').then((r) => r.json()).catch(() => null)
if (!health?.model_configured || !health?.index_available) throw new Error(`The API at ${API} is not ready: ${JSON.stringify(health)}`)

const chat = {}
const resume = {}
const search = {}

const first = await ask('first question', () => post('/chat', chatBody(Q.departure)), (r) => r.status === 'answered' && r.citations.length > 0 && readsWell(r))
chat[Q.departure] = first
chat[Q.followUp] = await ask('follow-up', () => post('/chat', chatBody(Q.followUp, first.thread_id)), (r) => r.status === 'answered' && readsWell(r))

const vague = await ask('vague question', () => post('/chat', chatBody(Q.vague)), (r) => r.status === 'needs_clarification')
chat[Q.vague] = vague
resume[Q.vagueReply] = await ask(
  'clarification reply',
  async () => {
    // a retry needs a fresh paused thread, because a resumed one is no longer paused
    const paused = chat[Q.vague]
    return post('/chat/resume', { thread_id: paused.thread_id, interrupt_id: paused.clarification.interrupt_id, message: Q.vagueReply })
  },
  (r) => r.status === 'answered' && readsWell(r),
)

chat[Q.recipe] = await ask('out of scope', () => post('/chat', chatBody(Q.recipe)), (r) => r.status === 'out_of_scope')
chat[Q.camel] = await ask('no evidence', () => post('/chat', chatBody(Q.camel)), (r) => r.status === 'insufficient_evidence')

search[searchKey(Q.search, 'hybrid', null, null)] = await ask('search hybrid', () => post('/search', searchBody('hybrid')), (r) => r.results.length > 0)
search[searchKey(Q.search, 'lexical', null, null)] = await ask('search lexical', () => post('/search', searchBody('lexical')), (r) => r.results.length > 0)
search[searchKey(Q.search, 'lexical', 2026, 'Law')] = await ask(
  'search with no match',
  () => post('/search', searchBody('lexical', { year: 2026, doc_type: 'Law' })),
  (r) => r.results.length === 0,
)
// the demo switches mode and then adds the filters, so the page asks for lexical + filters; a hybrid + filters key keeps a re-ordered flow working too
search[searchKey(Q.search, 'hybrid', 2026, 'Law')] = await post('/search', searchBody('hybrid', { year: 2026, doc_type: 'Law' }))

mkdirSync(new URL('./fixtures/', import.meta.url), { recursive: true })
writeFileSync(
  new URL('./fixtures/responses.json', import.meta.url),
  JSON.stringify({ capturedAt: new Date().toISOString(), source: API, chat, resume, search }, null, 2) + '\n',
)
console.log('Saved demo/fixtures/responses.json')
