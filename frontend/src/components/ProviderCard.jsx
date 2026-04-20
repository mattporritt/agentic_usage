const VARIANTS = {
  anthropic: {
    label: 'Anthropic',
    accent: 'text-purple-400',
    border: 'border-purple-500/20',
    glow: 'shadow-purple-500/10',
    dot: 'bg-purple-400 shadow-[0_0_8px_2px_rgba(168,85,247,0.5)]',
    badge: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
  },
  openai: {
    label: 'OpenAI',
    accent: 'text-green-400',
    border: 'border-green-500/20',
    glow: 'shadow-green-500/10',
    dot: 'bg-green-400 shadow-[0_0_8px_2px_rgba(74,222,128,0.5)]',
    badge: 'bg-green-500/10 text-green-400 border-green-500/30',
  },
  claude_code: {
    label: 'Claude Code',
    accent: 'text-orange-400',
    border: 'border-orange-500/20',
    glow: 'shadow-orange-500/10',
    dot: 'bg-orange-400 shadow-[0_0_8px_2px_rgba(251,146,60,0.5)]',
    badge: 'bg-orange-500/10 text-orange-400 border-orange-500/30',
  },
}

const ERROR_LABELS = {
  admin_key_required: 'Admin key required',
  invalid_key: 'Invalid key',
  error: 'Error',
}

function fmt(n) {
  if (n == null) return '—'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return n.toLocaleString()
}

function StatRow({ label, value, accent }) {
  return (
    <div className="flex items-baseline justify-between py-1 border-b border-gray-800/60 last:border-0">
      <span className="text-xs text-gray-500 uppercase tracking-wider">{label}</span>
      <span className={`text-sm font-semibold tabular-nums ${accent}`}>{value}</span>
    </div>
  )
}

export function ProviderCard({ variant, apiData, logData }) {
  const v = VARIANTS[variant]

  // Claude Code card — different data shape
  if (variant === 'claude_code') {
    if (!apiData?.configured) {
      return (
        <div className={`bg-gray-900 rounded-xl border ${v.border} p-6 shadow-lg ${v.glow} flex flex-col gap-4`}>
          <div className="flex items-center justify-between">
            <h2 className={`text-sm font-bold tracking-widest uppercase ${v.accent}`}>{v.label}</h2>
            <span className={`text-xs px-2 py-0.5 rounded border ${v.badge}`}>Not found</span>
          </div>
          <p className="text-xs text-gray-600">{apiData?.error || 'Set CLAUDE_CODE_DIR in .env'}</p>
        </div>
      )
    }

    const today = apiData?.today
    return (
      <div className={`bg-gray-900 rounded-xl border ${v.border} p-6 shadow-lg ${v.glow} flex flex-col gap-4`}>
        <div className="flex items-center justify-between">
          <h2 className={`text-sm font-bold tracking-widest uppercase ${v.accent}`}>{v.label}</h2>
          <div className={`w-1.5 h-1.5 rounded-full ${v.dot}`} />
        </div>
        <div className="space-y-0.5">
          <StatRow label="Total today" value={fmt(today?.total_tokens)} accent={v.accent} />
          <StatRow label="Input" value={fmt(today?.input_tokens)} accent="text-gray-300" />
          <StatRow label="Cache read" value={fmt(today?.cache_read_tokens)} accent="text-gray-300" />
          <StatRow label="Output" value={fmt(today?.output_tokens)} accent="text-gray-300" />
        </div>
        {apiData?.by_model && Object.keys(apiData.by_model).length > 0 && (
          <div className="text-xs text-gray-600 space-y-0.5 pt-1 border-t border-gray-800/60">
            {Object.entries(apiData.by_model).map(([model, usage]) => (
              <div key={model} className="flex justify-between">
                <span className="truncate text-gray-600">{model.replace('claude-', '')}</span>
                <span className="text-gray-500 tabular-nums">{fmt(usage.output_tokens)} out</span>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  // Anthropic / OpenAI cards
  const mergedToday = {
    input_tokens: (apiData?.today?.input_tokens ?? 0) + (logData?.today?.input_tokens ?? 0),
    output_tokens: (apiData?.today?.output_tokens ?? 0) + (logData?.today?.output_tokens ?? 0),
    total_tokens: (apiData?.today?.total_tokens ?? 0) + (logData?.today?.total_tokens ?? 0),
  }

  if (!apiData?.configured) {
    return (
      <div className={`bg-gray-900 rounded-xl border ${v.border} p-6 shadow-lg ${v.glow} flex flex-col gap-4`}>
        <div className="flex items-center justify-between">
          <h2 className={`text-sm font-bold tracking-widest uppercase ${v.accent}`}>{v.label}</h2>
          <span className={`text-xs px-2 py-0.5 rounded border ${v.badge}`}>Not configured</span>
        </div>
        <p className="text-xs text-gray-600">Set {variant.toUpperCase()}_ADMIN_KEY in .env to enable.</p>
      </div>
    )
  }

  if (apiData?.error_type) {
    const label = ERROR_LABELS[apiData.error_type] ?? 'Error'
    const hint = apiData.error_type === 'admin_key_required'
      ? 'An org-level admin API key is required for usage data.'
      : 'A standard API key was provided — an admin key (sk-ant-admin-…) is required.'
    return (
      <div className={`bg-gray-900 rounded-xl border ${v.border} p-6 shadow-lg ${v.glow} flex flex-col gap-4`}>
        <div className="flex items-center justify-between">
          <h2 className={`text-sm font-bold tracking-widest uppercase ${v.accent}`}>{v.label}</h2>
          <span className="text-xs px-2 py-0.5 rounded border bg-yellow-500/10 text-yellow-400 border-yellow-500/30">
            {label}
          </span>
        </div>
        <p className="text-xs text-gray-600">{hint}</p>
      </div>
    )
  }

  return (
    <div className={`bg-gray-900 rounded-xl border ${v.border} p-6 shadow-lg ${v.glow} flex flex-col gap-4`}>
      <div className="flex items-center justify-between">
        <h2 className={`text-sm font-bold tracking-widest uppercase ${v.accent}`}>{v.label}</h2>
        <div className={`w-1.5 h-1.5 rounded-full ${v.dot}`} />
      </div>

      <div className="space-y-0.5">
        <StatRow label="Total today" value={fmt(mergedToday.total_tokens)} accent={v.accent} />
        <StatRow label="Input" value={fmt(mergedToday.input_tokens)} accent="text-gray-300" />
        <StatRow label="Output" value={fmt(mergedToday.output_tokens)} accent="text-gray-300" />
      </div>

      {logData?.today?.total_tokens > 0 && (
        <p className="text-xs text-gray-600">
          + {fmt(logData.today.total_tokens)} from local logs
        </p>
      )}
    </div>
  )
}
