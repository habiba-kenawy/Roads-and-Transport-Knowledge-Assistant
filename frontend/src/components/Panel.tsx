import type { ReactNode } from 'react'

// The white card used for blocks of content: an uppercase title with the small red rule under it.
export function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-border bg-card p-5 text-card-foreground shadow-sm">
      <h2 className="text-sm font-bold uppercase tracking-wider">{title}</h2>
      <div className="mt-2 mb-4 h-0.5 w-10 bg-accent-red" aria-hidden />
      {children}
    </section>
  )
}
