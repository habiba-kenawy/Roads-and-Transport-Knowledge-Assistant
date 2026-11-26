import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

// types.ts is our hand-kept copy of the API's shapes. src/api/contract.json is what the backend says they are
// (python -m scripts.export_openapi). If they disagree, the page would send or read the wrong fields.

interface Shape {
  properties: string[]
  required: string[]
}

const contract: Record<string, Shape & { enums: Record<string, string[]> }> = JSON.parse(
  readFileSync(new URL('./api/contract.json', import.meta.url), 'utf-8'),
)
const source = readFileSync(new URL('./types.ts', import.meta.url), 'utf-8')

// Read the interfaces out of types.ts: top-level `name: type` or `name?: type` lines inside each `export interface Name {` block.
function declaredInterfaces(text: string): Record<string, Shape> {
  const found: Record<string, Shape> = {}
  let current: Shape | null = null
  for (const line of text.split('\n')) {
    const opening = line.match(/^export interface (\w+) \{/)
    if (opening) {
      current = { properties: [], required: [] }
      found[opening[1]] = current
      continue
    }
    if (line.startsWith('}')) current = null
    const field = current && line.match(/^ {2}(\w+)(\?)?:/)
    if (current && field) {
      current.properties.push(field[1])
      if (!field[2]) current.required.push(field[1])
    }
  }
  return found
}

function declaredValues(text: string, name: string): string[] {
  const line = text.split('\n').find((l) => l.startsWith(`export type ${name} =`)) ?? ''
  return [...line.matchAll(/'([^']+)'/g)].map((match) => match[1])
}

const TS_NAME_TO_API_NAME: Record<string, string> = { ValidationIssue: 'ValidationError' } // FastAPI's own name for a 422 entry
const interfaces = declaredInterfaces(source)

describe('types.ts matches the API contract', () => {
  it('declares the interfaces the page uses', () => {
    expect(Object.keys(interfaces).length).toBeGreaterThanOrEqual(10)
  })

  it.each(Object.keys(interfaces))('%s has the same fields, and the same required ones', (name) => {
    const api = contract[TS_NAME_TO_API_NAME[name] ?? name]
    expect(api, `${name} does not exist in the API contract`).toBeDefined()
    expect([...interfaces[name].properties].sort()).toEqual(api.properties)
    expect([...interfaces[name].required].sort()).toEqual(api.required)
  })

  it('lists the same search modes and answer statuses', () => {
    expect(declaredValues(source, 'SearchMode')).toEqual(contract.SearchRequest.enums.mode)
    expect(declaredValues(source, 'ChatStatus')).toEqual(contract.ChatResponse.enums.status)
  })
})
