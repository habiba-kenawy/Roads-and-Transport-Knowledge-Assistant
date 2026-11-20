import { Button } from '@/components/ui/button'

// Chunk 1 proof page (replaced by the real shell in chunk 2): shows every theme token and one shadcn component.
const SWATCHES = [
  { name: 'brand', className: 'bg-brand text-white' },
  { name: 'ink', className: 'bg-ink text-white' },
  { name: 'panel', className: 'bg-panel text-white' },
  { name: 'accent-red', className: 'bg-accent-red text-white' },
  { name: 'surface', className: 'bg-surface text-ink border border-border' },
]

export default function App() {
  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="text-2xl font-bold uppercase tracking-wide">TAREEQ</h1>
      <div className="mt-1 h-0.5 w-12 bg-accent-red" />
      <p className="mt-4 text-muted-foreground">
        Theme check. API base URL: <code>{import.meta.env.VITE_API_BASE_URL}</code>
      </p>
      <ul className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-5">
        {SWATCHES.map((s) => (
          <li key={s.name} className={`${s.className} p-4 text-sm font-medium`}>
            {s.name}
          </li>
        ))}
      </ul>
      <Button className="mt-6">Button from shadcn</Button>
    </main>
  )
}
