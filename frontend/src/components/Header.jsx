export function Header({ lastUpdated, onRefresh, refreshing }) {
  const formatted = lastUpdated
    ? new Date(lastUpdated).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '—'

  return (
    <header style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '14px 28px',
      borderBottom: '1px solid var(--border)',
      background: 'rgba(7,13,28,0.9)',
      backdropFilter: 'blur(12px)',
      WebkitBackdropFilter: 'blur(12px)',
      position: 'sticky',
      top: 0,
      zIndex: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{
          width: 8, height: 8, borderRadius: '50%',
          background: refreshing ? '#eab308' : '#22d3a0',
          boxShadow: refreshing
            ? '0 0 10px 3px rgba(234,179,8,0.5)'
            : '0 0 10px 3px rgba(34,211,160,0.45)',
          animation: 'glow-pulse 2.4s ease-in-out infinite',
          flexShrink: 0,
          transition: 'background 0.3s, box-shadow 0.3s',
        }} />
        <h1 style={{
          margin: 0,
          fontSize: 'var(--fs-label)',
          fontWeight: 700,
          letterSpacing: '0.22em',
          textTransform: 'uppercase',
          fontFamily: 'var(--font-display)',
          color: 'var(--text-1)',
        }}>
          Agentic Usage
        </h1>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <span style={{
          fontSize: 'var(--fs-micro)',
          color: 'var(--text-3)',
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
        }}>
          updated {formatted}
        </span>

        <button
          onClick={onRefresh}
          disabled={refreshing}
          title="Force refresh"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '5px 12px',
            fontSize: 'var(--fs-micro)',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            fontFamily: 'var(--font-data)',
            color: refreshing ? 'var(--text-3)' : 'var(--text-2)',
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            cursor: refreshing ? 'not-allowed' : 'pointer',
            transition: 'all 0.15s ease',
            outline: 'none',
          }}
          onMouseEnter={e => { if (!refreshing) e.currentTarget.style.borderColor = 'var(--border-hi)'; e.currentTarget.style.color = 'var(--text-1)' }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = refreshing ? 'var(--text-3)' : 'var(--text-2)' }}
        >
          <svg
            width="11" height="11" viewBox="0 0 16 16" fill="none"
            stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
            style={{ animation: refreshing ? 'spin 0.8s linear infinite' : 'none' }}
          >
            <path d="M13.5 2.5A7 7 0 1 0 15 8" />
            <polyline points="15 2 15 6 11 6" />
          </svg>
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>
    </header>
  )
}
