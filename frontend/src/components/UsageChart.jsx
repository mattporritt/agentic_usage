import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

function buildChartData(anthropicHistory, openaiHistory, days) {
  const now = new Date()
  const dateMap = {}

  // Generate last N date keys
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now)
    d.setUTCDate(d.getUTCDate() - i)
    const key = d.toISOString().slice(0, 10)
    dateMap[key] = { date: key, anthropic: 0, openai: 0 }
  }

  const merge = (history, field) => {
    ;(history || []).forEach(({ date, input_tokens = 0, output_tokens = 0 }) => {
      if (dateMap[date]) dateMap[date][field] = input_tokens + output_tokens
    })
  }

  merge(anthropicHistory, 'anthropic')
  merge(openaiHistory, 'openai')

  return Object.values(dateMap).map((d) => ({
    ...d,
    date: d.date.slice(5), // MM-DD for display
  }))
}

function fmtY(value) {
  if (value >= 1_000_000) return (value / 1_000_000).toFixed(1) + 'M'
  if (value >= 1_000) return (value / 1_000).toFixed(0) + 'K'
  return value
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 text-xs shadow-xl">
      <p className="text-gray-400 mb-2">{label}</p>
      {payload.map((p) => (
        <div key={p.dataKey} className="flex gap-3 justify-between">
          <span style={{ color: p.color }}>{p.name}</span>
          <span className="text-gray-200 tabular-nums">{fmtY(p.value)}</span>
        </div>
      ))}
    </div>
  )
}

export function UsageChart({ anthropicHistory, openaiHistory, days }) {
  const chartData = buildChartData(anthropicHistory, openaiHistory, days)

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={chartData} margin={{ top: 8, right: 24, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
        <XAxis
          dataKey="date"
          tick={{ fill: '#6b7280', fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: '#374151' }}
        />
        <YAxis
          tickFormatter={fmtY}
          tick={{ fill: '#6b7280', fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          width={48}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          wrapperStyle={{ fontSize: 12, color: '#9ca3af', paddingTop: 8 }}
        />
        <Line
          type="monotone"
          dataKey="anthropic"
          name="Anthropic"
          stroke="#a855f7"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: '#a855f7' }}
        />
        <Line
          type="monotone"
          dataKey="openai"
          name="OpenAI"
          stroke="#4ade80"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: '#4ade80' }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
