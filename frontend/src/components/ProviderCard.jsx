// ─── Pricing table (per 1M tokens, USD) ──────────────────────────────────────
const PRICING = {
  opus:          { input: 15,   output: 75,   cacheRead: 1.50 },
  sonnet:        { input: 3,    output: 15,   cacheRead: 0.30 },
  haiku:         { input: 0.80, output: 4,    cacheRead: 0.08 },
  'gpt-4o':      { input: 2.50, output: 10,   cacheRead: 0 },
  'gpt-4o-mini': { input: 0.15, output: 0.60, cacheRead: 0 },
  default:       { input: 3,    output: 15,   cacheRead: 0.30 },
}

function pricingFor(name = '') {
  const n = name.toLowerCase()
  if (n.includes('opus'))    return PRICING.opus
  if (n.includes('sonnet'))  return PRICING.sonnet
  if (n.includes('haiku'))   return PRICING.haiku
  if (n.includes('4o-mini')) return PRICING['gpt-4o-mini']
  if (n.includes('4o'))      return PRICING['gpt-4o']
  return PRICING.default
}

// ─── Derived metrics ──────────────────────────────────────────────────────────

function estimateCost(today, byModel) {
  if (!today) return null
  const entries = Object.entries(byModel || {})
  let avgIn = 3, avgOut = 15, avgCR = 0.30
  if (entries.length > 0) {
    let tIn = 0, tOut = 0, wIn = 0, wOut = 0, wCR = 0
    for (const [m, u] of entries) {
      const p = pricingFor(m)
      tIn  += u.input_tokens  || 0
      tOut += u.output_tokens || 0
      wIn  += (u.input_tokens  || 0) * p.input
      wOut += (u.output_tokens || 0) * p.output
      wCR  += (u.input_tokens  || 0) * p.cacheRead
    }
    if (tIn  > 0) { avgIn = wIn / tIn; avgCR = wCR / tIn }
    if (tOut > 0)   avgOut = wOut / tOut
  }
  const cr = today.cache_read_tokens ?? today.cached_tokens ?? 0
  return ((today.input_tokens || 0) * avgIn + (today.output_tokens || 0) * avgOut + cr * avgCR) / 1_000_000
}

function cacheEfficiency(today, isClaudeCode) {
  if (!today) return null
  if (isClaudeCode) {
    const cr = today.cache_read_tokens || 0
    const inp = today.input_tokens || 0
    const tot = inp + cr
    return tot > 0 ? Math.round(cr / tot * 100) : null
  }
  const cached = today.cached_tokens || 0
  const inp = today.input_tokens || 0
  return inp > 0 ? Math.round(cached / inp * 100) : null
}

function cacheSavings(today, byModel) {
  const cr = today?.cache_read_tokens
  if (!cr) return null
  let topModel = null, topCount = 0
  for (const [m, u] of Object.entries(byModel || {})) {
    if ((u.input_tokens || 0) > topCount) { topCount = u.input_tokens; topModel = m }
  }
  const p = topModel ? pricingFor(topModel) : PRICING.sonnet
  return cr * (p.input - p.cacheRead) / 1_000_000
}

function calcBurnRate(pct, windowHours, resetIso) {
  if (!resetIso || !pct || !windowHours) return null
  const resetMs   = new Date(resetIso).getTime()
  const now       = Date.now()
  const remainMs  = Math.max(0, resetMs - now)
  const elapsedMs = windowHours * 3_600_000 - remainMs
  if (elapsedMs < 60_000) return null
  const rate = pct / elapsedMs
  const projPct = pct + rate * remainMs
  if (projPct >= 100) return { willExceed: true,  projPct: Math.round(projPct), msToLimit: (100 - pct) / rate }
  return               { willExceed: false, projPct: Math.round(projPct) }
}

/** Normalise window hours into a short label: 5h → "5h", 168h → "7d" */
function windowLabel(hours) {
  if (hours < 24) return `${hours}h`
  return `${Math.round(hours / 24)}d`
}

function getWindows(usage) {
  if (!usage) return []
  return [
    usage.five_hour  && { hours: 5,                        pct: usage.five_hour.utilization,  reset: usage.five_hour.resets_at },
    usage.seven_day  && { hours: 168,                      pct: usage.seven_day.utilization,  reset: usage.seven_day.resets_at },
    usage.primary    && { hours: usage.primary.window_hours,   pct: usage.primary.used_percent,   reset: usage.primary.reset_at },
    usage.secondary  && { hours: usage.secondary.window_hours, pct: usage.secondary.used_percent, reset: usage.secondary.reset_at },
  ].filter(Boolean)
}

// ─── Formatters ───────────────────────────────────────────────────────────────

function fmt(n) {
  if (n == null || n === 0) return '0'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M'
  if (n >= 1_000)     return (n / 1_000).toFixed(1) + 'K'
  return n.toLocaleString()
}

function fmtUsd(n) {
  if (n == null) return null
  return n < 0.01 ? '<$0.01' : `$${n.toFixed(2)}`
}

/**
 * Returns { relative, absolute } for a reset ISO timestamp.
 * relative: "in 45m" | "in 4h 59m" | "in 2d 3h"
 * absolute: "Mon 5 May, 14:30"
 */
function formatReset(iso) {
  if (!iso) return null
  const diff = new Date(iso) - Date.now()
  if (diff <= 0) return { relative: 'now', absolute: null }

  const totalMins = Math.floor(diff / 60_000)
  const d = Math.floor(totalMins / 1440)
  const h = Math.floor((totalMins % 1440) / 60)
  const m = totalMins % 60

  const relative = d > 0 ? `in ${d}d ${h}h` : h > 0 ? `in ${h}h ${m}m` : `in ${m}m`

  const abs = new Date(iso)
  const absolute = abs.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })
    + ', ' + abs.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

  return { relative, absolute }
}

function fmtMs(ms) {
  if (!ms || ms <= 0) return 'now'
  const h = Math.floor(ms / 3_600_000)
  const m = Math.floor((ms % 3_600_000) / 60_000)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

// ─── Design tokens ────────────────────────────────────────────────────────────

const VARIANTS = {
  claude_code: {
    label:      'Claude Code',
    accent:     '#f97316',
    accentText: '#fb923c',
    accentDim:  'rgba(249,115,22,0.08)',
    accentMed:  'rgba(249,115,22,0.22)',
  },
  codex: {
    label:      'Codex',
    accent:     '#10b981',
    accentText: '#34d399',
    accentDim:  'rgba(16,185,129,0.08)',
    accentMed:  'rgba(16,185,129,0.22)',
  },
}

// ─── Primitives ───────────────────────────────────────────────────────────────

function Label({ children, style }) {
  return (
    <span style={{
      fontSize: 'var(--fs-micro)',
      letterSpacing: '0.11em',
      textTransform: 'uppercase',
      color: 'var(--text-3)',
      display: 'block',
      ...style,
    }}>
      {children}
    </span>
  )
}

function Rule() {
  return <div style={{ height: 1, background: 'var(--border)', margin: '0 -24px' }} />
}

/** Section header with a subtle background band for contrast */
function SectionHeader({ children }) {
  return (
    <div style={{
      margin: '0 -24px',
      padding: '7px 24px',
      background: 'rgba(255,255,255,0.025)',
      borderTop: '1px solid var(--border)',
      borderBottom: '1px solid var(--border)',
    }}>
      <Label style={{ color: 'var(--text-2)' }}>{children}</Label>
    </div>
  )
}

// ─── Stat grid ────────────────────────────────────────────────────────────────

function StatGrid({ today, isClaudeCode, efficiency, accentText }) {
  const cacheLabel = 'Cached'
  const cacheValue = fmt(isClaudeCode ? today.cache_read_tokens : today.cached_tokens)
  const cells = [
    { label: 'Input',    value: fmt(today.input_tokens),  hi: false },
    { label: cacheLabel, value: cacheValue,               hi: false },
    { label: 'Output',   value: fmt(today.output_tokens), hi: true  },
    ...(efficiency != null
      ? [{ label: 'Cache Hit', value: `${efficiency}%`, hi: efficiency > 50 }]
      : [{ label: 'Total',     value: fmt(today.total_tokens), hi: false }]
    ),
  ]
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px 24px' }}>
      {cells.map(c => (
        <div key={c.label}>
          <Label>{c.label}</Label>
          <div style={{
            fontSize: 'var(--fs-value)',
            fontWeight: 500,
            marginTop: 4,
            color: c.hi ? accentText : 'var(--text-1)',
            fontVariantNumeric: 'tabular-nums',
          }}>
            {c.value}
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── Rate limit bar with burn-rate projection ─────────────────────────────────

function RateBar({ w, accent }) {
  const burn      = calcBurnRate(w.pct, w.hours, w.reset)
  const reset     = formatReset(w.reset)
  const fillColor = w.pct >= 90 ? '#ef4444' : w.pct >= 70 ? '#eab308' : accent
  const ghostColor = !burn ? null
    : burn.willExceed    ? 'rgba(239,68,68,0.28)'
    : burn.projPct >= 80 ? 'rgba(234,179,8,0.25)'
    : `${accent}30`
  const burnColor = !burn ? 'var(--text-3)'
    : burn.willExceed    ? '#ef4444'
    : burn.projPct >= 80 ? '#eab308'
    : 'var(--text-3)'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8 }}>
        <Label style={{ whiteSpace: 'nowrap' }}>{windowLabel(w.hours)} window</Label>
        <div style={{ textAlign: 'right' }}>
          <span style={{ fontSize: 'var(--fs-body)', color: 'var(--text-2)', fontVariantNumeric: 'tabular-nums' }}>
            {w.pct.toFixed(0)}%
          </span>
          {reset && (
            <span style={{ fontSize: 'var(--fs-micro)', color: 'var(--text-3)', marginLeft: 8 }}>
              resets {reset.relative}
            </span>
          )}
        </div>
      </div>

      <div style={{
        position: 'relative', height: 5, borderRadius: 3, overflow: 'hidden',
        background: 'rgba(255,255,255,0.06)',
      }}>
        {ghostColor && (
          <div style={{
            position: 'absolute', top: 0, left: 0, bottom: 0,
            width: `${Math.min(burn.projPct, 100)}%`,
            borderRadius: 3, background: ghostColor,
          }} />
        )}
        <div style={{
          position: 'absolute', top: 0, left: 0, bottom: 0,
          width: `${Math.min(w.pct, 100)}%`,
          borderRadius: 3, background: fillColor,
          transition: 'width 0.8s cubic-bezier(0.4,0,0.2,1)',
        }} />
      </div>

      {/* Burn rate + absolute reset date on same row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8 }}>
        {burn ? (
          <span style={{ fontSize: 'var(--fs-micro)', color: burnColor, fontVariantNumeric: 'tabular-nums' }}>
            {burn.willExceed
              ? `⚡ limit in ~${fmtMs(burn.msToLimit)}`
              : `→ proj ${burn.projPct}% at reset`
            }
          </span>
        ) : <span />}
        {reset?.absolute && (
          <span style={{ fontSize: 'var(--fs-micro)', color: 'var(--text-3)', whiteSpace: 'nowrap' }}>
            {reset.absolute}
          </span>
        )}
      </div>
    </div>
  )
}

// ─── Quota bar ────────────────────────────────────────────────────────────────

function QuotaSection({ quota, accent }) {
  const { plan, hard_limit_usd, used_usd } = quota
  const pct = hard_limit_usd > 0 ? Math.min(100, (used_usd / hard_limit_usd) * 100) : null
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <Label>{plan || 'Subscription'}</Label>
        {hard_limit_usd != null
          ? <span style={{ fontSize: 'var(--fs-body)', color: 'var(--text-2)' }}>{fmtUsd(used_usd)} / {fmtUsd(hard_limit_usd)}</span>
          : <span style={{ fontSize: 'var(--fs-body)', color: 'var(--text-3)' }}>{fmtUsd(used_usd) ?? '—'} used</span>
        }
      </div>
      {pct != null && (
        <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2 }}>
          <div style={{ height: '100%', width: `${pct}%`, background: pct > 85 ? '#ef4444' : accent, borderRadius: 2 }} />
        </div>
      )}
    </div>
  )
}

// ─── Model breakdown footer ───────────────────────────────────────────────────

function ModelFooter({ byModel }) {
  const entries = Object.entries(byModel || {})
    .filter(([, u]) => u.output_tokens > 0 || u.input_tokens > 0)
    .sort((a, b) => (b[1].output_tokens + b[1].input_tokens) - (a[1].output_tokens + a[1].input_tokens))
  if (!entries.length) return null
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {entries.map(([model, u]) => (
        <div key={model} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--fs-body)' }}>
          <span style={{
            color: 'var(--text-2)',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '46%',
          }}>
            {model.replace(/^(claude|gpt)-/, '')}
          </span>
          <span style={{ color: 'var(--text-3)', fontVariantNumeric: 'tabular-nums' }}>
            {fmt(u.input_tokens)} in · {fmt(u.output_tokens)} out
          </span>
        </div>
      ))}
    </div>
  )
}

// ─── Main card ────────────────────────────────────────────────────────────────

export function ProviderCard({ variant, data }) {
  const v = VARIANTS[variant]
  if (!v) return null

  if (!data?.configured) {
    return (
      <div className="card-enter" style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderTop: `2px solid ${v.accent}28`,
        borderRadius: 12,
        padding: '20px 24px',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <span style={{
            fontSize: 'var(--fs-label)', fontWeight: 700, letterSpacing: '0.18em',
            textTransform: 'uppercase', fontFamily: 'var(--font-display)',
            color: v.accentText,
          }}>
            {v.label}
          </span>
          <span style={{
            fontSize: 'var(--fs-micro)', padding: '3px 8px',
            border: '1px solid var(--border-hi)', borderRadius: 3,
            color: 'var(--text-3)', letterSpacing: '0.1em', textTransform: 'uppercase',
          }}>
            Not found
          </span>
        </div>
        <p style={{ margin: 0, fontSize: 'var(--fs-body)', color: 'var(--text-2)', lineHeight: 1.5 }}>
          {data?.error || 'Install the CLI or set the directory in .env'}
        </p>
      </div>
    )
  }

  const today        = data?.today    ?? {}
  const byModel      = data?.by_model ?? {}
  const isClaudeCode = variant === 'claude_code'
  const windows      = getWindows(data?.usage)
  const cost         = estimateCost(today, byModel)
  const efficiency   = cacheEfficiency(today, isClaudeCode)
  const savings      = cacheSavings(today, byModel)
  const hasModels    = Object.keys(byModel).length > 0

  return (
    <div className="card-enter" style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderTop: `2px solid ${v.accent}`,
      borderRadius: 12,
      overflow: 'hidden',
      boxShadow: `0 0 60px ${v.accentDim}, inset 0 1px 0 rgba(255,255,255,0.04)`,
      display: 'flex',
      flexDirection: 'column',
    }}>

      {/* ── Card header ── */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 24px',
        background: v.accentDim,
        borderBottom: '1px solid var(--border)',
      }}>
        <span style={{
          fontSize: 'var(--fs-label)', fontWeight: 700, letterSpacing: '0.18em',
          textTransform: 'uppercase', fontFamily: 'var(--font-display)',
          color: v.accentText,
        }}>
          {v.label}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {data?.plan?.subscription_type && (
            <span style={{
              fontSize: 'var(--fs-micro)', letterSpacing: '0.12em', textTransform: 'uppercase',
              padding: '3px 8px', borderRadius: 3,
              border: `1px solid ${v.accent}35`,
              color: v.accentText,
            }}>
              {data.plan.subscription_type}
            </span>
          )}
          <div style={{
            width: 7, height: 7, borderRadius: '50%',
            background: v.accent,
            boxShadow: `0 0 9px 3px ${v.accentMed}`,
            animation: 'glow-pulse 2.4s ease-in-out infinite',
          }} />
        </div>
      </div>

      {/* ── Hero row ── */}
      <div style={{
        display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16,
        padding: '20px 24px 18px',
      }}>
        <div>
          <div style={{
            fontSize: 'var(--fs-hero)',
            fontWeight: 700, lineHeight: 1,
            color: v.accentText, fontFamily: 'var(--font-display)',
            fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.02em',
          }}>
            {fmt(today.total_tokens)}
          </div>
          <Label style={{ marginTop: 6 }}>tokens today</Label>
        </div>
        {cost != null && (
          <div style={{ textAlign: 'right' }}>
            <div style={{
              fontSize: 'var(--fs-large)',
              fontWeight: 600, lineHeight: 1,
              color: 'var(--text-1)', fontFamily: 'var(--font-display)',
              fontVariantNumeric: 'tabular-nums',
            }}>
              {fmtUsd(cost)}
            </div>
            <Label style={{ marginTop: 6 }}>est. cost today</Label>
          </div>
        )}
      </div>

      {/* ── Token breakdown ── */}
      <Rule />
      <div style={{ padding: '16px 24px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        <StatGrid today={today} isClaudeCode={isClaudeCode} efficiency={efficiency} accentText={v.accentText} />
        {savings != null && savings > 0.01 && (
          <p style={{ margin: 0, fontSize: 'var(--fs-micro)', color: 'var(--text-3)', lineHeight: 1.4 }}>
            ↓ cache saved ~{fmtUsd(savings)} vs uncached today
          </p>
        )}
      </div>

      {/* ── Rate limits ── */}
      {windows.length > 0 && (
        <>
          <SectionHeader>Rate limit usage</SectionHeader>
          <div style={{ padding: '14px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
            {windows.map((w, i) => <RateBar key={i} w={w} accent={v.accent} />)}
            {data?.usage?.extra_usage && (
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--fs-body)', color: 'var(--text-3)', paddingTop: 4 }}>
                <span>Extra credits</span>
                <span style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--text-2)' }}>
                  {fmtUsd(data.usage.extra_usage.used_credits)} / {fmtUsd(data.usage.extra_usage.monthly_limit)} {data.usage.extra_usage.currency}
                </span>
              </div>
            )}
          </div>
        </>
      )}

      {/* ── Quota ── */}
      {data?.quota && (
        <>
          <SectionHeader>Billing quota</SectionHeader>
          <div style={{ padding: '14px 24px' }}>
            <QuotaSection quota={data.quota} accent={v.accent} />
          </div>
        </>
      )}

      {/* ── Model breakdown ── */}
      {hasModels && (
        <>
          <SectionHeader>30-day by model</SectionHeader>
          <div style={{ padding: '14px 24px' }}>
            <ModelFooter byModel={byModel} />
          </div>
        </>
      )}

    </div>
  )
}
