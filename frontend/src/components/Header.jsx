export function Header({ lastUpdated }) {
  const formatted = lastUpdated
    ? new Date(lastUpdated).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '—'

  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
      <div className="flex items-center gap-3">
        <div className="w-2 h-2 rounded-full bg-green-400 shadow-[0_0_8px_2px_rgba(74,222,128,0.5)] animate-pulse" />
        <h1 className="text-lg font-bold tracking-widest uppercase text-gray-100">
          Agentic Usage
        </h1>
      </div>
      <div className="text-xs text-gray-500 tracking-wider">
        UPDATED {formatted}
      </div>
    </header>
  )
}
