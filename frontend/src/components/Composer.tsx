import { ArrowUp } from 'lucide-react'
import type { FormEvent, KeyboardEvent } from 'react'

import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { ANY, DOC_TYPES, MAX_MESSAGE_CHARS, MODES, TOP_K_MAX, TOP_K_MIN, YEARS, type Controls, type SearchMode } from '@/lib/options'

interface Props {
  question: string
  onQuestionChange: (text: string) => void
  controls: Controls
  onControlsChange: (next: Controls) => void
  onSubmit: () => void
  submitLabel: string
}

// Lists open ABOVE their chip, over the text box, so they can never cover another chip (the chips and the send button are the
// bottom rows of the composer). If there is no room above, the browser flips them below. max-h-64: a long list scrolls.
const LIST = { position: 'popper', side: 'top', align: 'start', sideOffset: 6, className: 'max-h-64' } as const

// A small rounded "chip" look for the dropdowns inside the composer.
const CHIP = 'h-8! gap-1 rounded-full border-transparent bg-surface px-3 text-xs hover:bg-accent [&_svg]:size-3.5'

// The big rounded question box: text area on top, the search options as chips underneath, the send button on the right.
// Enter sends, Shift+Enter starts a new line. It only holds what the user typed and chose; sending comes later.
export function Composer({ question, onQuestionChange, controls, onControlsChange, onSubmit, submitLabel }: Props) {
  const set = (patch: Partial<Controls>) => onControlsChange({ ...controls, ...patch })
  const canSend = question.trim().length > 0

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (canSend) onSubmit()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      handleSubmit(event)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="w-full rounded-2xl border border-border bg-card p-3 text-left shadow-md focus-within:border-brand focus-within:ring-2 focus-within:ring-brand/20"
    >
      <textarea
        value={question}
        onChange={(e) => onQuestionChange(e.target.value)}
        onKeyDown={handleKeyDown}
        maxLength={MAX_MESSAGE_CHARS}
        rows={2}
        aria-label="Your question"
        placeholder="Ask about Roads and Transport legislation..."
        className="w-full resize-none bg-transparent px-2 py-1.5 text-base text-ink outline-none placeholder:text-muted-foreground"
      />

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Select value={controls.mode} onValueChange={(v) => set({ mode: v as SearchMode })}>
          <SelectTrigger className={`${CHIP} w-22 px-2 sm:w-44 sm:px-3`} aria-label="Search mode">
            <SelectValue>{MODES.find((m) => m.value === controls.mode)?.short}</SelectValue>
          </SelectTrigger>
          <SelectContent {...LIST}>
            {MODES.map((m) => (
              <SelectItem key={m.value} value={m.value}>
                {m.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={controls.year === null ? ANY : String(controls.year)} onValueChange={(v) => set({ year: v === ANY ? null : Number(v) })}>
          <SelectTrigger className={`${CHIP} w-22 px-2 sm:w-36 sm:px-3`} aria-label="Year">
            <SelectValue />
          </SelectTrigger>
          <SelectContent {...LIST}>
            <SelectItem value={ANY}>Any year</SelectItem>
            {YEARS.map((y) => (
              <SelectItem key={y} value={String(y)}>
                {y}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={controls.docType ?? ANY} onValueChange={(v) => set({ docType: v === ANY ? null : v })}>
          <SelectTrigger className={`${CHIP} w-22 px-2 sm:w-36 sm:px-3`} aria-label="Document type">
            <SelectValue />
          </SelectTrigger>
          <SelectContent {...LIST}>
            <SelectItem value={ANY}>Any type</SelectItem>
            {DOC_TYPES.map((t) => (
              <SelectItem key={t} value={t}>
                {t}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="flex h-8 items-center gap-2 rounded-full bg-surface px-3 text-xs">
          <span className="whitespace-nowrap">Top-k {controls.topK}</span>
          <Slider
            aria-label="Top-k"
            min={TOP_K_MIN}
            max={TOP_K_MAX}
            step={1}
            value={[controls.topK]}
            onValueChange={([v]) => set({ topK: v })}
            className="w-20 **:data-[slot=slider-track]:bg-border"
          />
        </div>

        <Button
          type="submit"
          size="icon"
          disabled={!canSend}
          aria-label={submitLabel}
          title={submitLabel}
          className="ml-auto size-10 rounded-full bg-brand text-white hover:bg-brand/90 disabled:border disabled:border-border disabled:bg-card disabled:text-muted-foreground disabled:opacity-100"
        >
          <ArrowUp aria-hidden />
        </Button>
      </div>
    </form>
  )
}
