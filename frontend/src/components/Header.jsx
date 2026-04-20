export function Header({ lastUpdated }) {
  const formatted = lastUpdated
    ? new Date(lastUpdated).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '—'

  return (
    <header style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '16px 28px',
      borderBottom: '1px solid var(--border)',
      background: 'rgba(7,12,26,0.88)',
      backdropFilter: 'blur(12px)',
      WebkitBackdropFilter: 'blur(12px)',
      position: 'sticky',
      top: 0,
      zIndex: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: '#22d3a0',
          boxShadow: '0 0 10px 3px rgba(34,211,160,0.45)',
          animation: 'glow-pulse 2.4s ease-in-out infinite',
          flexShrink: 0,
        }} />
        <h1 style={{
          margin: 0,
          fontSize: 13,
          fontWeight: 700,
          letterSpacing: '0.22em',
          textTransform: 'uppercase',
          fontFamily: 'var(--font-display)',
          color: 'var(--text-1)',
        }}>
          Agentic Usage
        </h1>
      </div>

      <div style={{
        fontSize: 11,
        color: 'var(--text-3)',
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
      }}>
        updated {formatted}
      </div>
    </header>
  )
}
