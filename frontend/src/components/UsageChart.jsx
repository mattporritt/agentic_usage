import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'

function buildChartData(claudeCodeHistory, codexHistory, days) {
  const now = new Date()
  const dateMap = {}
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now)
    d.setUTCDate(d.getUTCDate() - i)
    const key = d.toISOString().slice(0, 10)
    dateMap[key] = { date: key, claude_code: 0, codex: 0 }
  }
  ;(claudeCodeHistory || []).forEach(({ date, output_tokens = 0 }) => {
    if (dateMap[date]) dateMap[date].claude_code = output_tokens
  })
  ;(codexHistory || []).forEach(({ date, input_tokens = 0, output_tokens = 0 }) => {
    if (dateMap[date]) dateMap[date].codex = input_tokens + output_tokens
  })
  return Object.values(dateMap).map(d => ({ ...d, date: d.date.slice(5) }))
}

function fmtY(v) {
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + 'M'
  if (v >= 1_000)     return (v / 1_000).toFixed(0) + 'K'
  return v
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: '#0b1228',
      border: '1px solid rgba(255,255,255,0.11)',
      borderRadius: 8,
      padding: '10px 14px',
      fontSize: 11,
      boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
      fontFamily: 'var(--font-data)',
    }}>
      <p style={{ color: 'var(--text-2)', margin: '0 0 8px', letterSpacing: '0.05em' }}>{label}</p>
      {payload.map(p => (
        <div key={p.dataKey} style={{ display: 'flex', justifyContent: 'space-between', gap: 16, marginBottom: 3 }}>
          <span style={{ color: p.color }}>{p.name}</span>
          <span style={{ color: 'var(--text-1)', fontVariantNumeric: 'tabular-nums' }}>{fmtY(p.value)}</span>
        </div>
      ))}
    </div>
  )
}

export function UsageChart({ claudeCodeHistory, codexHistory, days }) {
  const chartData = buildChartData(claudeCodeHistory, codexHistory, days)

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="4 4" stroke="rgba(255,255,255,0.04)" />
        <XAxis
          dataKey="date"
          tick={{ fill: '#6b7f99', fontSize: 11, fontFamily: 'var(--font-data)' }}
          tickLine={false}
          axisLine={{ stroke: 'rgba(255,255,255,0.07)' }}
        />
        <YAxis
          tickFormatter={fmtY}
          tick={{ fill: '#6b7f99', fontSize: 11, fontFamily: 'var(--font-data)' }}
          tickLine={false}
          axisLine={false}
          width={48}
        />
        <Tooltip content={<CustomTooltip />} cursor={{ stroke: 'rgba(255,255,255,0.07)', strokeWidth: 1 }} />
        <Legend
          wrapperStyle={{
            fontSize: 12, color: '#8fa2bb', paddingTop: 12,
            fontFamily: 'var(--font-data)', letterSpacing: '0.05em',
          }}
        />
        <Line type="monotone" dataKey="claude_code" name="Claude Code"
          stroke="#f97316" strokeWidth={1.5} dot={false}
          activeDot={{ r: 3, fill: '#f97316', strokeWidth: 0 }}
        />
        <Line type="monotone" dataKey="codex" name="Codex"
          stroke="#10b981" strokeWidth={1.5} dot={false}
          activeDot={{ r: 3, fill: '#10b981', strokeWidth: 0 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
