import { useEffect, useState } from "react"
import { getDomainPacks } from "../api"

// The backend's "active" pack is a global, mutable setting (see domain_pack.py) — any user
// can flip it at any time. Polling here means a task submitted from this screen pins
// whichever pack was actually showing in the UI a moment ago, not a stale value from when
// the page first loaded minutes earlier.
export function useActiveDomainPack(intervalMs = 15000) {
  const [pack, setPack]       = useState(null)   // null = no pack active (generic)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      try {
        const r = await getDomainPacks()
        if (!cancelled) setPack(r.data.find(p => p.active) || null)
      } catch {
        if (!cancelled) setPack(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    poll()
    const t = setInterval(poll, intervalMs)
    return () => { cancelled = true; clearInterval(t) }
  }, [intervalMs])

  return { pack, loading }
}
