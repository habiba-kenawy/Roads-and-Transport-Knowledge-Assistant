// What the demo asks and where it runs. Shared by capture-fixtures.js (asks the real backend) and record.js (replays the answers).
export const API = process.env.DEMO_API ?? 'http://127.0.0.1:8010'
export const APP = process.env.DEMO_APP ?? 'http://localhost:5180/'

export const QUESTIONS = {
  departure: 'How much is the departure fee for passengers leaving through Dubai airports, and who is exempt from it?', // the first example card
  followUp: 'Who is exempt from it?',
  vague: 'What is the fine?',
  vagueReply: 'the fees for passengers leaving through Dubai airports',
  recipe: 'What is a good recipe for pasta carbonara?',
  camel: 'What is the fine for parking a camel outside a mosque in Dubai?',
  search: 'departure fee airports',
}

// The key a recorded /search answer is stored under.
export const searchKey = (query, mode, year, docType) => [query, mode, year ?? '', docType ?? ''].join('|')

export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

export async function isUp(url) {
  try {
    return (await fetch(url, { signal: AbortSignal.timeout(2500) })).ok
  } catch {
    return false
  }
}
