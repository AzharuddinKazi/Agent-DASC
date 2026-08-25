import { useEffect, useState } from "react"
import { getTasks } from "../../api"
import { brand } from "../../config/brand"
import { useAuth } from "../../hooks/useAuth"
import { useHealth } from "../../hooks/useHealth"
import { useFeatureFlags } from "../../hooks/useFeatureFlags"
import { statusMeta } from "../../lib/taskStatus"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { MessageSquare, Package, Database, ShieldCheck, LogOut } from "lucide-react"

const CHECK_LABELS = { database: "Database", docker: "Sandbox", llm: "Model" }

function elapsed(created_at) {
  if (!created_at) return "just now"
  const s = Math.floor((Date.now() - new Date(created_at)) / 1000)
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return `${Math.floor(s / 3600)}h ago`
}

export default function Sidebar({ onNew, currentTaskId, onSelect, onDomainPacks, onData, activeView }) {
  const [tasks, setTasks] = useState([])
  const { user, signOut } = useAuth()
  const { health, loading: healthLoading } = useHealth()
  // Defaults true while the first poll is in flight so the link doesn't flash in/out on
  // load — matches domain_packs' own backend default of "enabled until told otherwise".
  const { flags: featureFlags } = useFeatureFlags()
  const domainPacksEnabled = featureFlags.domain_packs !== false
  // demo_mode defaults to *off* (unlike domain_packs above) — it's an operator-toggled
  // showcase mode, not a normally-on feature, so an in-flight first poll should hide this
  // link rather than flash it on for everyone by default.
  const demoModeEnabled = featureFlags.demo_mode === true
  // Guests (name-only login, no Google email — see backend/main.py's auth_guest) have no
  // email; fall back to their name so the sidebar isn't left blank for them.
  const email = user?.email || user?.name || ""
  const initials = email.slice(0, 2).toUpperCase()

  useEffect(() => {
    const load = async () => {
      try { const r = await getTasks(); setTasks(r.data) }
      catch (e) { console.error(e) }
    }
    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="flex flex-col h-full bg-sidebar text-sidebar-foreground">

      {/* Brand / Logo — click to return home */}
      <button
        onClick={onNew}
        className="h-14 flex items-center px-4 border-b border-sidebar-border shrink-0 cursor-pointer hover:bg-accent/60 transition-colors text-left"
      >
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center shrink-0">
            <span className="text-label font-black text-primary-foreground leading-none">{brand.appShortCode}</span>
          </div>
          <div className="min-w-0">
            <p className="text-sm font-bold text-foreground tracking-tight leading-none">{brand.appName}</p>
            <p className="text-label text-muted-foreground mt-0.5 truncate">{brand.tagline}</p>
          </div>
        </div>
      </button>

      {/* Nav section */}
      <div className="px-3 py-3 shrink-0 flex flex-col gap-0.5">
        <button
          onClick={onNew}
          className="flex items-center gap-2.5 px-3 py-2 rounded-md bg-accent text-accent-foreground font-semibold text-body cursor-pointer"
        >
          <MessageSquare className="w-4 h-4 shrink-0" />
          New Analysis
        </button>
        {onDomainPacks && domainPacksEnabled && (
          <button
            onClick={onDomainPacks}
            className={`flex items-center gap-2.5 px-3 py-2 rounded-md font-medium text-body cursor-pointer transition-colors ${
              activeView === "domainPacks"
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
            }`}
          >
            <Package className="w-4 h-4 shrink-0" />
            Domain Packs
          </button>
        )}
        {onData && demoModeEnabled && (
          <button
            onClick={onData}
            className={`flex items-center gap-2.5 px-3 py-2 rounded-md font-medium text-body cursor-pointer transition-colors ${
              activeView === "data"
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
            }`}
          >
            <Database className="w-4 h-4 shrink-0" />
            Available Data
          </button>
        )}
        {user?.is_admin && (
          // admin.html is a separate app entirely (its own build entry, own login/session
          // check — see AdminApp.jsx), not a client-side route of this SPA, so this is a
          // plain link rather than one of the onX callbacks the buttons above use. Opens
          // in a new tab so switching to it doesn't lose whatever's in progress here.
          <a
            href="/admin.html"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2.5 px-3 py-2 rounded-md font-medium text-body cursor-pointer transition-colors text-muted-foreground hover:bg-accent/60 hover:text-foreground"
          >
            <ShieldCheck className="w-4 h-4 shrink-0" />
            Admin Panel
          </a>
        )}
      </div>

      <Separator />

      {/* History */}
      <ScrollArea className="flex-1 min-h-0 px-3 pt-3 pb-3">
        <p className="text-label font-semibold uppercase text-muted-foreground mb-2 px-1">
          Recent
        </p>

        <div className="flex flex-col gap-0.5">
          {tasks.length === 0 && (
            <p className="text-xs text-muted-foreground px-2 py-3">No analyses yet</p>
          )}
          {tasks.map(task => {
            const active = task.task_id === currentTaskId
            const isReport = task.task_type === "report"
            return (
              <button
                key={task.task_id}
                onClick={() => onSelect(task.task_id, task.query, task.task_type)}
                className={`w-full text-left px-3 py-2.5 rounded-md text-sm transition-colors cursor-pointer ${
                  active
                    ? "bg-accent text-accent-foreground font-medium"
                    : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="line-clamp-2 leading-snug text-body mb-1 flex-1">{task.query}</p>
                  <span className={`shrink-0 w-4 h-4 rounded flex items-center justify-center text-label font-bold ${
                    isReport ? "bg-purple-100 text-purple-700" : "bg-blue-100 text-blue-700"
                  }`}>
                    {(isReport ? brand.modeLabels.report : brand.modeLabels.qa)[0]}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-label text-muted-foreground tabular-nums">
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${statusMeta(task.status).dot}`} />
                  <span>{elapsed(task.created_at)}</span>
                </div>
              </button>
            )
          })}
        </div>
      </ScrollArea>

      <Separator />

      {/* User footer */}
      <div className="px-3 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center shrink-0">
            <span className="text-label font-bold text-primary-foreground">{initials}</span>
          </div>
          <div className="min-w-0">
            <p className="text-xs font-semibold text-foreground leading-none truncate">{email}</p>
          </div>
        </div>
        <Button variant="ghost" size="icon-sm" className="text-muted-foreground shrink-0" onClick={signOut} title="Sign out">
          <LogOut className="w-3.5 h-3.5" />
        </Button>
      </div>

      {/* System status */}
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="px-4 py-2 flex items-center gap-2 border-t border-sidebar-border shrink-0 cursor-default">
            <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
              healthLoading  ? "bg-neutral-400 animate-pulse" :
              health?.status === "ok" ? "bg-success" : "bg-danger"
            }`} />
            <span className="text-label text-muted-foreground">
              {healthLoading ? "Checking systems…" : health?.status === "ok" ? "All systems normal" : "Degraded performance"}
            </span>
          </div>
        </TooltipTrigger>
        <TooltipContent side="top">
          <div className="flex flex-col gap-1">
            {Object.keys(CHECK_LABELS).map(key => {
              const check = health?.checks?.[key]
              return (
                <div key={key} className="flex items-center gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                    !check ? "bg-neutral-400" : check.status === "ok" ? "bg-success" : "bg-danger"
                  }`} />
                  <span>{CHECK_LABELS[key]}</span>
                </div>
              )
            })}
          </div>
        </TooltipContent>
      </Tooltip>
    </div>
  )
}
