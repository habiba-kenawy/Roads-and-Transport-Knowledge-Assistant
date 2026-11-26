// Every score the API returns has a type, and the types are on different scales: they must never be added, compared across
// kinds, or shown as how sure the system is. These names say what each number is and where it comes from.

const SCORES: Record<string, string> = {
  bm25: 'Keyword score (BM25)',
  cosine: 'Meaning similarity (cosine)',
  rrf: 'Fusion score (RRF, from ranks only)',
  llm_relevance_0_10: 'Reranker relevance, 0 to 10',
}

const STAGES: Record<string, string> = {
  lexical: 'Keyword ranking',
  semantic: 'Meaning ranking',
  fused_rrf: 'Fused ranking (not reranked)',
  reranked: 'Reranked',
}

export const scoreLabel = (type: string) => SCORES[type] ?? type
export const stageLabel = (stage: string) => STAGES[stage] ?? stage

// Scores are shown with the precision that fits their scale.
export const formatScore = (type: string, value: number) => (type === 'llm_relevance_0_10' ? String(Math.round(value)) : value.toFixed(3))
