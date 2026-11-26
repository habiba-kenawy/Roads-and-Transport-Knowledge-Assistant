import axios from 'axios'

import type { ChatRequest, ChatResponse, ResumeRequest, SearchRequest, SearchResponse } from '@/types'

// One axios instance for the whole app: the server address comes from VITE_API_BASE_URL (frontend/.env).
// A full answer normally takes 8-14 s (planning, search, reranking, answer are separate model calls), so the limit is generous.
// Every function rejects with an AxiosError on failure; screens turn it into a friendly message with toFriendlyError().
const REQUEST_TIMEOUT_MS = 90_000

const baseURL = import.meta.env.VITE_API_BASE_URL
if (!baseURL) throw new Error('VITE_API_BASE_URL is not set: copy frontend/.env.example to frontend/.env')

const http = axios.create({ baseURL, timeout: REQUEST_TIMEOUT_MS })

// `signal` lets the caller cancel a request that is no longer wanted (for example on "New conversation").
export async function sendChat(body: ChatRequest, signal?: AbortSignal): Promise<ChatResponse> {
  return (await http.post<ChatResponse>('/chat', body, { signal })).data
}

export async function resumeChat(body: ResumeRequest, signal?: AbortSignal): Promise<ChatResponse> {
  return (await http.post<ChatResponse>('/chat/resume', body, { signal })).data
}

export async function searchPassages(body: SearchRequest, signal?: AbortSignal): Promise<SearchResponse> {
  return (await http.post<SearchResponse>('/search', body, { signal })).data
}
