import { useCallback, useEffect, useState } from "react"
import { getMe, logout as apiLogout } from "../api"

// Real Google-login session state (see TASKS.md "Google OAuth login + Admin Control
// Panel") — replaces the local-single-user stub. There's no signIn() here: the Google
// Sign In button (see components/app/Login.jsx) drives login directly by POSTing its
// credential to the backend, then calling refresh() below. Session lives in an httponly
// cookie the backend sets, so there's nothing to read/write on this side beyond asking
// "who am I" on load.
export function useAuth() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const r = await getMe()
      setUser(r.data)
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  // Session-restore-on-load — same "call the loader on mount" shape as useHealth.js's
  // poll(), just with a cancellation guard (matches that file's own pattern) so a
  // fast unmount can't set state on a gone component.
  useEffect(() => {
    let cancelled = false
    getMe()
      .then(r => { if (!cancelled) setUser(r.data) })
      .catch(() => { if (!cancelled) setUser(null) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  const signOut = async () => {
    try { await apiLogout() } catch { /* cookie clears server-side either way */ }
    setUser(null)
  }

  return { user, loading, refresh, signOut }
}
