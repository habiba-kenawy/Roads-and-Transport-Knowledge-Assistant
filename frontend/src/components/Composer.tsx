import { ArrowUp, Loader2Icon } from 'lucide-react'
import type { FormEvent, KeyboardEvent, ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { ANY, DOC_TYPES, MAX_MESSAGE_CHARS, MODES, TOP_K_MAX, TOP_K_MIN, YEARS, isSearchMode, type Controls } from '@/lib/options'

interface Props {
  question: string
  onQuestionChange: (text: string) => void
  controls: Controls
  onControlsChange: (next: Controls) => void
  onSubmit: () => void
  submitLabel: string
  busy: boolean // a request is in flight: sending is blocked until the answer arrives
  placeholder: string
}

// Lists open ABOVE their chip so they can never cover another chip (the chips and the send button are the bottom rows).
// If there is no room above, the browser flips them below. max-h-64: a long list scrolls.
const LIST = { position: 'popper', side: 'top', align: 'start', sideOffset: 6, className: 'max-h-64' } as const

const CHIP = 'h-8! gap-1 rounded-full border-transparent bg-surface px-3 text-xs hover:bg-accent [&_svg]:size-3.5'
const SEND_BUTTON =
  'ml-auto size-10 rounded-full bg-brand text-white hover:bg-brand/90 disabled:border disabled:border-border disabled:bg-card disabled:text-muted-foreground disabled:opacity-100'

interface ChipSelectProps {
  label: string
  value: string
  onChange: (value: string) => void
  display?: string // what the chip shows; the selected item's own text when omitted
  widthClass: string // wide-screen width; phones use a fixed narrow chip so all three fit on one row
  children: ReactNode
}

function ChipSelect({ label, value, onChange, display, widthClass, children }: ChipSelectProps) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className={`${CHIP} w-22 px-2 sm:px-3 ${widthClass}`} aria-label={label}>
        <SelectValue>{display}</SelectValue>
      </SelectTrigger>
      <SelectContent {...LIST}>{children}</SelectContent>
    </Select>
  )
}

// The question box: text area, the search options as chips, and the send button. Enter sends, Shift+Enter starts a new line.
export function Composer({ question, onQuestionChange, controls, onControlsChange, onSubmit, submitLabel, busy, placeholder }: Props) {
  const set = (patch: Partial<Controls>) => onControlsChange({ ...controls, ...patch })
  const canSend = question.trim().length > 0 && !busy

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
        placeholder={placeholder}
        className="w-full resize-none bg-transparent px-2 py-1.5 text-base text-ink outline-none placeholder:text-muted-foreground"
      />

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <ChipSelect
          label="Search mode"
          value={controls.mode}
          onChange={(value) => isSearchMode(value) && set({ mode: value })}
          display={MODES.find((m) => m.value === controls.mode)?.short}
          widthClass="sm:w-44"
        >
          {MODES.map((m) => (
            <SelectItem key={m.value} value={m.value}>
              {m.label}
            </SelectItem>
          ))}
        </ChipSelect>

        <ChipSelect
          label="Year"
          value={controls.year === null ? ANY : String(controls.year)}
          onChange={(value) => set({ year: value === ANY ? null : Number(value) })}
          widthClass="sm:w-36"
        >
          <SelectItem value={ANY}>Any year</SelectItem>
          {YEARS.map((year) => (
            <SelectItem key={year} value={String(year)}>
              {year}
            </SelectItem>
          ))}
        </ChipSelect>

        <ChipSelect
          label="Document type"
          value={controls.docType ?? ANY}
          onChange={(value) => set({ docType: value === ANY ? null : value })}
          widthClass="sm:w-36"
        >
          <SelectItem value={ANY}>Any type</SelectItem>
          {DOC_TYPES.map((type) => (
            <SelectItem key={type} value={type}>
              {type}
            </SelectItem>
          ))}
        </ChipSelect>

        <div className="flex h-8 items-center gap-2 rounded-full bg-surface px-3 text-xs">
          <span className="whitespace-nowrap">Top-k {controls.topK}</span>
          <Slider
            aria-label="Top-k"
            min={TOP_K_MIN}
            max={TOP_K_MAX}
            step={1}
            value={[controls.topK]}
            onValueChange={([topK]) => set({ topK })}
            className="w-20 **:data-[slot=slider-track]:bg-border"
          />
        </div>

        <Button
          type="submit"
          size="icon"
          disabled={!canSend}
          aria-label={busy ? 'Working' : submitLabel}
          title={busy ? 'Working' : submitLabel}
          className={SEND_BUTTON}
        >
          {busy ? <Loader2Icon className="animate-spin" aria-hidden /> : <ArrowUp aria-hidden />}
        </Button>
      </div>
    </form>
  )
}
