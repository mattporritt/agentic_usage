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
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        minHeight: '100svh',
        fontSize: 10, letterSpacing: '0.2em', textTransform: 'uppercase',
        color: 'var(--text-3)', fontFamily: 'var(--font-display)',
      }}>
        Loading…
      </div>
    )
  }

  if (error && !data) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        minHeight: '100svh', fontSize: 12, color: '#ef4444',
        fontFamily: 'var(--font-data)',
      }}>
        Could not reach backend: {error}
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100svh' }}>
      <Header lastUpdated={data?.last_updated} />

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 20, padding: 20 }}>

        {/* Provider cards */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          <ProviderCard variant="claude_code" data={data?.claude_code} />
          <ProviderCard variant="codex"       data={data?.codex} />
        </div>

        {/* Chart */}
        <div style={{
          flex: 1,
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          padding: '18px 20px',
          display: 'flex', flexDirection: 'column', gap: 16,
          minHeight: 300,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{
              fontSize: 9, letterSpacing: '0.18em', textTransform: 'uppercase',
              fontFamily: 'var(--font-display)', color: 'var(--text-3)',
            }}>
              Output Tokens / Day
            </span>
            <div style={{ display: 'flex', gap: 3 }}>
              {TIME_WINDOWS.map(w => (
                <button
                  key={w}
                  onClick={() => setDays(w)}
                  style={{
                    padding: '4px 10px',
                    fontSize: 9,
                    letterSpacing: '0.1em',
                    textTransform: 'uppercase',
                    borderRadius: 4,
                    border: '1px solid',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                    fontFamily: 'var(--font-data)',
                    ...(days === w
                      ? { background: 'rgba(255,255,255,0.08)', borderColor: 'var(--border-hi)', color: 'var(--text-1)' }
                      : { background: 'transparent', borderColor: 'transparent', color: 'var(--text-3)' }
                    ),
                  }}
                >
                  {w}D
                </button>
              ))}
            </div>
          </div>

          <div style={{ height: 260 }}>
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
