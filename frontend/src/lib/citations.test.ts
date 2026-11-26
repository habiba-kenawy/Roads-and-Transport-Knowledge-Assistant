import { describe, expect, it } from 'vitest'

import { sentencesCiting, splitMarkers } from '@/lib/citations'

const ANSWER =
  'A fee of AED 75.00 is collected from every passenger [1]. Children under two are exempt [2]. Airlines collect it [1].\n\n' +
  'Note: "Law [7] of 2020" has the status "Repealed".\nThis is not legal advice.'

describe('splitMarkers', () => {
  it('turns [n] into markers and keeps the text between them', () => {
    const parts = splitMarkers('Fee is 75 [1]. Exempt [2].', 2)
    expect(parts.filter((p) => p.kind === 'marker')).toEqual([
      { kind: 'marker', n: 1 },
      { kind: 'marker', n: 2 },
    ])
    expect(parts.map((p) => (p.kind === 'text' ? p.text : `[${p.n}]`)).join('')).toBe('Fee is 75 [1]. Exempt [2].')
  })

  it('leaves a number that names no real source as plain text', () => {
    expect(splitMarkers(ANSWER, 2).filter((p) => p.kind === 'marker')).toHaveLength(3)
    expect(splitMarkers('see [0] and [3]', 2)).toEqual([{ kind: 'text', text: 'see [0] and [3]' }])
  })

  it('handles an empty text', () => {
    expect(splitMarkers('', 0)).toEqual([])
  })
})

describe('sentencesCiting', () => {
  it('returns every sentence that carries the marker, whole, even with full stops inside', () => {
    expect(sentencesCiting(ANSWER, 1)).toEqual(['A fee of AED 75.00 is collected from every passenger', 'Airlines collect it'])
    expect(sentencesCiting(ANSWER, 2)).toEqual(['Children under two are exempt'])
  })

  it('ignores the notes and the disclaimer after the first blank line', () => {
    expect(sentencesCiting(ANSWER, 7)).toEqual([])
  })

  it('returns nothing for a source no sentence cites', () => {
    expect(sentencesCiting(ANSWER, 3)).toEqual([])
  })
})
