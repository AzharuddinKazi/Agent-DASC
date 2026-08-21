import { useEffect, useState } from "react"
import { getFeatureFlags } from "../api"

// Being logged in (useAuth) and being an admin (ADMIN_EMAILS allowlist, checked
// server-side by auth.py:get_current_admin) are different things — this probes that
// distinction with the one authenticated call every admin screen needs anyway, rather
// than adding a dedicated "am I an admin" endpoint just to ask the same question twice.
export function useAdminAccess() {
  const [status, setStatus] = useState("checking")   // "checking" | "authorized" | "forbidden" | "error"
  const [flags, setFlags]   = useState({})

  useEffect(() => {
    let cancelled = false
    getFeatureFlags()
      .then(r => {
        if (cancelled) return
        setFlags(r.data)
        setStatus("authorized")
      })
      .catch(err => {
        if (cancelled) return
        setStatus(err?.response?.status === 403 ? "forbidden" : "error")
      })
    return () => { cancelled = true }
  }, [])

  return { status, flags }
}
