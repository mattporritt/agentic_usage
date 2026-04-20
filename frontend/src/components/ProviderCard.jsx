const VARIANTS = {
  claude_code: {
    label: 'Claude Code',
    accent: 'text-orange-400',
    border: 'border-orange-500/20',
    glow: 'shadow-orange-500/10',
    dot: 'bg-orange-400 shadow-[0_0_8px_2px_rgba(251,146,60,0.5)]',
  },
  codex: {
    label: 'Codex',
    accent: 'text-green-400',
    border: 'border-green-500/20',
    glow: 'shadow-green-500/10',
    dot: 'bg-green-400 shadow-[0_0_8px_2px_rgba(74,222,128,0.5)]',
  },
}

function fmt(n) {
  if (n == null || n === 0) return '0'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return n.toLocaleString()
}

function StatRow({ label, value, accent = 'text-gray-300' }) {
  return (
    <div className="flex items-baseline justify-between py-1.5 border-b border-gray-800/60 last:border-0">
      <span className="text-xs text-gray-500 uppercase tracking-wider">{label}</span>
      <span className={`text-sm font-semibold tabular-nums ${accent}`}>{value}</span>
    </div>
  )
}

function ModelFooter({ byModel }) {
  const entries = Object.entries(byModel || {})
    .filter(([, u]) => u.output_tokens > 0 || u.input_tokens > 0)
    .sort((a, b) => (b[1].output_tokens + b[1].input_tokens) - (a[1].output_tokens + a[1].input_tokens))
  if (!entries.length) return null
  return (
    <div className="text-xs space-y-0.5 pt-2 border-t border-gray-800/60">
      {entries.map(([model, usage]) => (
        <div key={model} className="flex justify-between text-gray-600">
          <span className="truncate">{model.replace(/^(claude|gpt)-/, '')}</span>
          <span className="tabular-nums text-gray-500 ml-2">
            {fmt(usage.input_tokens)} in · {fmt(usage.output_tokens)} out
          </span>
        </div>
      ))}
    </div>
  )
}

export function ProviderCard({ variant, data }) {
  const v = VARIANTS[variant]

  if (!v) return null

  if (!data?.configured) {
    return (
      <div className={`bg-gray-900 rounded-xl border ${v.border} p-6 shadow-lg flex flex-col gap-3`}>
        <div className="flex items-center justify-between">
          <h2 className={`text-sm font-bold tracking-widest uppercase ${v.accent}`}>{v.label}</h2>
          <span className={`text-xs px-2 py-0.5 rounded border bg-gray-800 text-gray-500 border-gray-700`}>
            Not found
          </span>
        </div>
        <p className="text-xs text-gray-600">{data?.error || 'Install the CLI or set the directory in .env'}</p>
      </div>
    )
  }

  const today = data?.today ?? {}
  const isClaudeCode = variant === 'claude_code'

  return (
    <div className={`bg-gray-900 rounded-xl border ${v.border} p-6 shadow-lg ${v.glow} flex flex-col gap-4`}>
      <div className="flex items-center justify-between">
        <h2 className={`text-sm font-bold tracking-widest uppercase ${v.accent}`}>{v.label}</h2>
        <div className={`w-1.5 h-1.5 rounded-full ${v.dot}`} />
      </div>

      <div className="space-y-0">
        <StatRow label="Total today" value={fmt(today.total_tokens)} accent={v.accent} />
        <StatRow label="Input" value={fmt(today.input_tokens)} />
        {isClaudeCode
          ? <StatRow label="Cache read" value={fmt(today.cache_read_tokens)} />
          : <StatRow label="Cached" value={fmt(today.cached_tokens)} />
        }
        <StatRow label="Output" value={fmt(today.output_tokens)} />
      </div>

      <ModelFooter byModel={data?.by_model} />
    </div>
  )
}
