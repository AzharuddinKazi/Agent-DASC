import { useCallback, useEffect, useState } from "react"
import { getAdminSystem } from "../api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Activity, Database, Container, Cpu, Gauge } from "lucide-react"

const CHECK_META = {
  database: { label: "Database", icon: Database },
  docker:   { label: "Sandbox",  icon: Container },
  llm:      { label: "Model",    icon: Cpu },
}

function CheckCard({ name, check }) {
  const meta = CHECK_META[name] || { label: name, icon: Activity }
  const Icon = meta.icon
  const ok = check.status === "ok"
  return (
    <Card>
      <CardContent className="p-4 flex items-center gap-3">
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${ok ? "bg-success/10" : "bg-danger/10"}`}>
          <Icon className={`w-4 h-4 ${ok ? "text-success" : "text-danger"}`} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-body font-medium text-foreground">{meta.label}</p>
          <p className="text-caption text-muted-foreground truncate">
            {ok ? `${check.latency_ms}ms` : (check.detail || "Unreachable")}
          </p>
        </div>
        <Badge variant="outline" className={ok ? "bg-success/10 text-success border-success/30" : "bg-danger/10 text-danger border-danger/30"}>
          {ok ? "OK" : "Down"}
        </Badge>
      </CardContent>
    </Card>
  )
}

// Single load-on-mount, no polling — same call FeatureFlagsPanel makes: this is a
// point-in-time snapshot an admin opens to check on, not a live dashboard someone leaves
// open. A manual refresh button covers the "did that just come back up" case.
export default function AdminSystemPanel() {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState("")

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const r = await getAdminSystem()
      setData(r.data)
      setError("")
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Failed to load system status")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div className="max-w-3xl mx-auto flex flex-col gap-6 w-full">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <Activity className="w-5 h-5 text-foreground" />
            <h2 className="text-display-sm font-bold text-foreground tracking-tight leading-tight">System</h2>
          </div>
          <p className="text-body text-muted-foreground leading-relaxed max-w-xl">
            Live health of every backend dependency, plus the runtime settings that affect
            every user's next request.
          </p>
        </div>
        <button
          onClick={load} disabled={loading}
          className="text-caption text-muted-foreground hover:text-foreground underline underline-offset-2 disabled:opacity-50"
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {data && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {Object.entries(data.checks).map(([name, check]) => (
              <CheckCard key={name} name={name} check={check} />
            ))}
          </div>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <Gauge className="w-4 h-4 text-foreground" />
                <CardTitle className="text-heading">Runtime settings</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="pt-0 flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="text-body text-muted-foreground">Concurrent pipeline slots</span>
                <span className="text-body font-medium text-foreground tabular-nums">
                  {data.concurrency.active} / {data.concurrency.max}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-body text-muted-foreground">LLM speed profile</span>
                <Badge variant="outline" className="capitalize">{data.llm_speed_profile.replace("_", " ")}</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-body text-muted-foreground">Feature flags</span>
                <div className="flex gap-1.5">
                  {Object.entries(data.feature_flags).map(([name, enabled]) => (
                    <Badge
                      key={name} variant="outline"
                      className={enabled ? "bg-success/10 text-success border-success/30" : "bg-muted text-muted-foreground border-border"}
                    >
                      {name}: {enabled ? "on" : "off"}
                    </Badge>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
