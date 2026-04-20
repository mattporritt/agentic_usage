import { useState } from 'react'
import { useStats } from './hooks/useStats'
import { Header } from './components/Header'
import { ProviderCard } from './components/ProviderCard'
import { UsageChart } from './components/UsageChart'

const TIME_WINDOWS = [7, 14, 30]

function mergeHistory(apiHistory, logHistory) {
  const map = {}
  ;(apiHistory || []).forEach(({ date, input_tokens = 0, output_tokens = 0 }) => {
    map[date] = { date, input_tokens, output_tokens }
  })
  ;(logHistory || []).forEach(({ date, input_tokens = 0, output_tokens = 0 }) => {
    if (map[date]) {
      map[date].input_tokens += input_tokens
      map[date].output_tokens += output_tokens
    } else {
      map[date] = { date, input_tokens, output_tokens }
    }
  })
  return Object.values(map).sort((a, b) => a.date.localeCompare(b.date))
}

export default function App() {
  const { data, error, loading } = useStats()
  const [days, setDays] = useState(7)

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

  const anthropicHistory = mergeHistory(data?.anthropic?.history, data?.logs?.anthropic?.history)
  const openaiHistory = mergeHistory(data?.openai?.history, data?.logs?.openai?.history)

  return (
    <div className="flex flex-col min-h-screen bg-gray-950">
      <Header lastUpdated={data?.last_updated} />

      <main className="flex-1 flex flex-col gap-6 p-6">
        {/* Provider cards */}
        <div className="grid grid-cols-2 gap-6">
          <ProviderCard
            variant="anthropic"
            apiData={data?.anthropic}
            logData={data?.logs?.anthropic}
          />
          <ProviderCard
            variant="openai"
            apiData={data?.openai}
            logData={data?.logs?.openai}
          />
        </div>

        {/* Chart panel */}
        <div className="flex-1 bg-gray-900 rounded-xl border border-gray-800 p-6 flex flex-col gap-4 min-h-[280px]">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-bold tracking-widest uppercase text-gray-500">
              Token Usage — Total Tokens / Day
            </h2>
            <div className="flex gap-1">
              {TIME_WINDOWS.map((w) => (
                <button
                  key={w}
                  onClick={() => setDays(w)}
                  className={`px-3 py-1 text-xs rounded tracking-wider transition-colors ${
                    days === w
                      ? 'bg-gray-700 text-gray-100'
                      : 'text-gray-500 hover:text-gray-300'
                  }`}
                >
                  {w}D
                </button>
              ))}
            </div>
          </div>
          <div className="flex-1">
            <UsageChart
              anthropicHistory={anthropicHistory}
              openaiHistory={openaiHistory}
              days={days}
            />
          </div>
        </div>
      </main>
    </div>
  )
}
