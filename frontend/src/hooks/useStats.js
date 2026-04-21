import { useState, useEffect, useCallback } from 'react'

const POLL_MS = 60_000

export function useStats() {
  const [data, setData]       = useState(null)
  const [error, setError]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const fetchStats = useCallback(async () => {
    try {
      const resp = await fetch('/api/stats')
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      setData(await resp.json())
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const forceRefresh = useCallback(async () => {
    setRefreshing(true)
    try {
      const resp = await fetch('/api/refresh', { method: 'POST' })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      setData(await resp.json())
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchStats()
    const id = setInterval(fetchStats, POLL_MS)
    return () => clearInterval(id)
  }, [fetchStats])

  return { data, error, loading, refreshing, forceRefresh }
}
