import { Panel } from '@/components/Panel'

// Plain-language explanation of what the assistant does and where it falls short. Static text.
export function AboutPage() {
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <Panel title="How it works">
        <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed">
          <li>Your question is read together with the conversation so far. If it is too vague, you are asked a short question first (at most twice).</li>
          <li>The assistant searches 45 official Roads and Transport documents (by keywords, by meaning, or both) and ranks the best passages.</li>
          <li>The answer is written only from those passages. Every sentence has a numbered citation that is checked against the stored text, and the
            assistant says so when the evidence is not enough.</li>
          <li>The Search Inspector shows the ranked passages and the score each one carries. Scores of different kinds cannot be compared and are not a
            measure of confidence.</li>
        </ul>
      </Panel>
      <Panel title="Limitations">
        <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed">
          <li>This is an unofficial student project and not legal advice. The documents are a limited set: not exhaustive and not guaranteed to be
            current. Status is shown as published on the Dubai Legislation Portal.</li>
          <li>Relevant passages can be missed. Check the cited page before relying on an answer.</li>
          <li>Amendments are not combined: a later amendment may change an article you are reading.</li>
          <li>Tables are flattened to plain text. Scanned documents and Arabic are not supported.</li>
          <li>A full answer takes several seconds.</li>
          <li>Your past conversations are kept only in this browser on this device. Deleting one here removes it from this list only.</li>
        </ul>
      </Panel>
    </div>
  )
}
