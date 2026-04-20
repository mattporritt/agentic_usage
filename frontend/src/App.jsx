import { useState } from 'react'
import { useStats } from './hooks/useStats'
import { Header } from './components/Header'
import { ProviderCard } from './components/ProviderCard'
import { UsageChart } from './components/UsageChart'

const TIME_WINDOWS = [7, 14, 30]

export default function App() {
  const { data, error, loading } = useStats()
  const [days, setDays] = useState(14)

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen text-gray-600 text-sm tracking-widest uppercase">
        Loading…
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="flex items-center justify-center min-h-screen text-red-500 text-sm">
        Could not reach backend: {error}
      </div>
    )
  }

  return (
    <div className="flex flex-col min-h-screen bg-gray-950">
      <Header lastUpdated={data?.last_updated} />

      <main className="flex-1 flex flex-col gap-6 p-6">
        <div className="grid grid-cols-2 gap-6">
          <ProviderCard variant="claude_code" data={data?.claude_code} />
          <ProviderCard variant="codex" data={data?.codex} />
        </div>

        <div className="flex-1 bg-gray-900 rounded-xl border border-gray-800 p-6 flex flex-col gap-4 min-h-[280px]">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-bold tracking-widest uppercase text-gray-500">
              Output Tokens / Day
            </h2>
            <div className="flex gap-1">
              {TIME_WINDOWS.map((w) => (
                <button
                  key={w}
                  onClick={() => setDays(w)}
                  className={`px-3 py-1 text-xs rounded tracking-wider transition-colors ${
                    days === w ? 'bg-gray-700 text-gray-100' : 'text-gray-500 hover:text-gray-300'
                  }`}
                >
                  {w}D
                </button>
              ))}
            </div>
          </div>
          <div className="h-64">
            <UsageChart
              claudeCodeHistory={data?.claude_code?.history}
              codexHistory={data?.codex?.history}
              days={days}
            />
          </div>
        </div>
      </main>
    </div>
  )
}
