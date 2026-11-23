// The shapes the backend sends and accepts. Copied field by field from the API's own OpenAPI document (GET /openapi.json),
// not guessed: `?` marks a field the API treats as optional, `| null` marks a field that can be null.

export type SearchMode = 'lexical' | 'semantic' | 'hybrid'
export type ChatStatus = 'answered' | 'needs_clarification' | 'insufficient_evidence' | 'out_of_scope'

export interface SearchFilters {
  year?: number | null
  doc_type?: string | null
}

// POST /chat  (message 1-2000 characters, top_k 1-20, unknown fields are rejected)
export interface ChatRequest {
  message: string
  thread_id?: string | null
  search_mode?: SearchMode
  top_k?: number
  filters?: SearchFilters
}

// POST /chat/resume  (thread_id: letters, digits, _ and -, 1-64 characters)
export interface ResumeRequest {
  thread_id: string
  interrupt_id: string
  message: string
}

// One verified source of an answer
export interface Citation {
  document_id: string
  chunk_id: string
  title: string
  source_url: string
  locator_type: string
  locator: string
}

// The pending question when status is needs_clarification
export interface Clarification {
  interrupt_id: string
  question: string
}

export interface ChatResponse {
  thread_id: string
  status: ChatStatus
  answer: string | null
  citations: Citation[]
  clarification: Clarification | null
  request_id: string
}

// POST /search  (query 1-500 characters, top_k 1-20)
export interface SearchRequest {
  query: string
  mode?: SearchMode
  filters?: SearchFilters
  top_k?: number
}

export interface SearchHit {
  rank: number
  score: number
  score_type: string
  stage: string
  chunk_id: string
  doc_id: string
  title: string
  source_url: string
  locator_type: string
  locator: string
  article: string | null
  year: number | null
  doc_type: string | null
  status: string | null
  text: string
}

export interface SearchResponse {
  mode: string
  ranking_stage: string
  filters_applied: SearchFilters
  results: SearchHit[]
  candidates_before_rerank?: string[] | null
  rerank_note?: string | null
}

// The body of a 422 answer (FastAPI): one entry per rejected field. 409/502/503 answers carry { detail: string } instead.
export interface ValidationIssue {
  loc: (string | number)[]
  msg: string
  type: string
  input?: unknown
  ctx?: Record<string, unknown>
}
