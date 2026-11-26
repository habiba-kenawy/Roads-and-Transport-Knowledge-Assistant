import { describe, expect, it } from 'vitest'

import { isSearchMode } from '@/lib/options'
import { formatScore, scoreLabel, stageLabel } from '@/lib/scores'

describe('score labels', () => {
  it('names every kind of score the API returns, so none is shown as a bare number', () => {
    expect(scoreLabel('bm25')).toMatch(/BM25/)
    expect(scoreLabel('cosine')).toMatch(/cosine/)
    expect(scoreLabel('rrf')).toMatch(/RRF/)
    expect(scoreLabel('llm_relevance_0_10')).toMatch(/0 to 10/)
  })

  it('shows an unknown kind as it is rather than hiding it', () => {
    expect(scoreLabel('something_new')).toBe('something_new')
    expect(stageLabel('something_new')).toBe('something_new')
  })

  it('gives the reranker score as a whole number and the others with three decimals', () => {
    expect(formatScore('llm_relevance_0_10', 9.6)).toBe('10')
    expect(formatScore('bm25', 17.8494)).toBe('17.849')
  })
})

describe('isSearchMode', () => {
  it('accepts the three modes and nothing else', () => {
    expect(['hybrid', 'lexical', 'semantic'].every(isSearchMode)).toBe(true)
    expect(isSearchMode('fuzzy')).toBe(false)
  })
})
