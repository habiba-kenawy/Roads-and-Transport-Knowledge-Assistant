import { FileCheck, Plane, Ship } from 'lucide-react'
import type { ReactNode } from 'react'

// Three real questions from our evaluation set: each is known to be answerable from the indexed documents.
const EXAMPLES = [
  {
    title: 'Airport departure fee',
    hint: 'How much it is and who is exempt',
    question: 'How much is the departure fee for passengers leaving through Dubai airports, and who is exempt from it?',
    Icon: Plane,
  },
  {
    title: 'Drone permit',
    hint: 'Importing or selling a drone in Dubai',
    question: 'Do I need a permit to import or sell a drone in Dubai?',
    Icon: FileCheck,
  },
  {
    title: 'Maritime accident',
    hint: 'What the authority must do after a report',
    question: 'What must the Dubai Maritime Authority do once a maritime accident has been reported to it?',
    Icon: Ship,
  },
]

// The first screen of the Assistant: brand mark, greeting, the composer (passed in) and the example questions.
export function EmptyState({ composer, onPick }: { composer: ReactNode; onPick: (question: string) => void }) {
  return (
    <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col items-center justify-center gap-6 px-4 py-8 text-center">
      <div className="brand-orb size-20 rounded-full sm:size-24" aria-hidden />
      <div>
        <p className="text-lg font-medium text-brand sm:text-xl">Roads and Transport Knowledge Assistant</p>
        <h1 className="mt-1 text-2xl font-bold text-ink sm:text-4xl">What would you like to know?</h1>
      </div>

      {composer}

      <ul className="grid w-full gap-3 sm:grid-cols-3">
        {EXAMPLES.map(({ title, hint, question, Icon }) => (
          <li key={title}>
            <button
              type="button"
              onClick={() => onPick(question)}
              className="flex h-full w-full flex-col gap-2 rounded-2xl border border-border bg-card p-4 text-left transition hover:border-brand hover:shadow-md"
            >
              <span className="flex size-8 items-center justify-center rounded-lg bg-accent text-brand">
                <Icon className="size-4" aria-hidden />
              </span>
              <span className="text-sm font-semibold text-ink">{title}</span>
              <span className="text-xs text-muted-foreground">{hint}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
