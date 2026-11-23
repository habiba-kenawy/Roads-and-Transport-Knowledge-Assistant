// The user's own message: a dark rounded bubble on the right. Shown as plain text (never as HTML).
export function UserBubble({ text }: { text: string }) {
  return (
    <div className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-panel px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap text-white">
      {text}
    </div>
  )
}
