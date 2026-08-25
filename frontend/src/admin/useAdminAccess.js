import { useEffect, useState } from "react"
import { getFeatureFlags } from "../api"

// Being logged in (useAuth) and being an admin (ADMIN_EMAILS allowlist, checked
// server-side by auth.py:get_current_admin) are different things — this probes that
// distinction with the one authenticated call every admin screen needs anyway, rather
// than adding a dedicated "am I an admin" endpoint just to ask the same question twice.
export function useAdminAccess() {
  // "checking" | "authorized" | "forbidden" | "signed_out" | "error"
  const [status, setStatus] = useState("checking")
  const [flags, setFlags]   = useState({})

  const recheck = () => {
    setStatus("checking")
    getFeatureFlags()
      .then(r => { setFlags(r.data); setStatus("authorized") })
      .catch(err => {
        const code = err?.response?.status
        setStatus(code === 403 ? "forbidden" : code === 401 ? "signed_out" : "error")
      })
  }

  useEffect(() => { recheck() }, [])

  return { status, flags, recheck }
}
