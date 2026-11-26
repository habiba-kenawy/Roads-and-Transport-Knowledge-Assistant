// The server writes every answer sentence as "<statement> [n]." where n is the number of a source in the citations list.
// These helpers only READ that text so the page can make the markers clickable; nothing here decides what is true.

type AnswerPart = { kind: 'text'; text: string } | { kind: 'marker'; n: number }

// Split the answer into plain text and source markers. A marker counts only if it names a real source (1..sourceCount);
// anything else that happens to look like "[7]" stays plain text.
export function splitMarkers(text: string, sourceCount: number): AnswerPart[] {
  const parts: AnswerPart[] = []
  let last = 0
  for (const match of text.matchAll(/\[(\d+)\]/g)) {
    const n = Number(match[1])
    if (n < 1 || n > sourceCount) continue
    if (match.index > last) parts.push({ kind: 'text', text: text.slice(last, match.index) })
    parts.push({ kind: 'marker', n })
    last = match.index + match[0].length
  }
  if (last < text.length) parts.push({ kind: 'text', text: text.slice(last) })
  return parts
}

// The sentences of the answer that cite source n. The answer body ends at the first blank line (the notes and the disclaimer follow it).
// Each sentence ends with its marker and a full stop, so "[n]." is the delimiter (a sentence may itself contain full stops, as in "AED 75.00").
export function sentencesCiting(answer: string, n: number): string[] {
  const body = answer.split('\n\n')[0]
  const found: string[] = []
  for (const match of body.matchAll(/(.+?)\s*\[(\d+)\]\./gs)) {
    if (Number(match[2]) === n) found.push(match[1].trim())
  }
  return found
}
