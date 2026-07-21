import { useEffect, useState } from "react"
import { checkHealth } from "../api"

export function useHealth(intervalMs = 30000) {
  const [health, setHealth]   = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      try {
        const r = await checkHealth()
        if (!cancelled) setHealth(r.data)
      } catch {
        if (!cancelled) setHealth({ status: "degraded", checks: {} })
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    poll()
    const t = setInterval(poll, intervalMs)
    return () => { cancelled = true; clearInterval(t) }
  }, [intervalMs])

  return { health, loading }
}
