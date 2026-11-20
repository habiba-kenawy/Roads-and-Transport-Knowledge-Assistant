// What the controls in the hero panel can hold. These mirror the backend's rules (search modes, top_k 1-20,
// message length 2000). The year and type lists are a copy of the corpus facts: the API has no endpoint that lists
// them, so they must be updated by hand if the corpus changes (a known limitation).

export type SearchMode = 'lexical' | 'semantic' | 'hybrid'

// label = what the list shows; short = what the chip shows (short enough for three chips to fit on one phone-width row)
export const MODES: { value: SearchMode; label: string; short: string }[] = [
  { value: 'hybrid', label: 'Hybrid', short: 'Hybrid' },
  { value: 'lexical', label: 'Lexical (keywords)', short: 'Lexical' },
  { value: 'semantic', label: 'Semantic (meaning)', short: 'Semantic' },
]

export const YEARS = [2026, 2025, 2024, 2023, 2022, 2020, 2016, 2012, 2011, 2010, 2008, 2007, 2006]
export const DOC_TYPES = ['Law', 'Regulation', 'Resolution']

export const TOP_K_MIN = 1
export const TOP_K_MAX = 20
export const MAX_MESSAGE_CHARS = 2000

// Radix Select cannot use an empty string as an item value, so "no filter" is this word.
export const ANY = 'any'

export interface Controls {
  mode: SearchMode
  year: number | null // null = no year filter
  docType: string | null // null = no type filter
  topK: number
}

export const DEFAULT_CONTROLS: Controls = { mode: 'hybrid', year: null, docType: null, topK: 5 }
