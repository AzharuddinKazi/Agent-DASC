import { useEffect, useState } from "react"
import { listFeatures } from "../api"

// Feature flags are DB-backed and can be flipped by an admin from the Admin page at any
// time (see feature_flags.py) — polling here (same pattern as useActiveDomainPack) means
// a flag flipped there is picked up by every other signed-in user's UI shortly after,
// not just at the moment this hook first mounted. Reads via listFeatures() (any
// signed-in user), not the admin-only getFeatureFlags() — see api.js.
export function useFeatureFlags(intervalMs = 15000) {
  const [flags, setFlags]     = useState({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      try {
        const r = await listFeatures()
        if (!cancelled) setFlags(r.data)
      } catch {
        // Leave the last-known flags in place rather than defaulting to "all disabled"
        // on a transient fetch error.
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    poll()
    const t = setInterval(poll, intervalMs)
    return () => { cancelled = true; clearInterval(t) }
  }, [intervalMs])

  return { flags, loading }
}
