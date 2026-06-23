import { useEffect, useState } from "react"
import { getTasks } from "../../api"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Plus, LayoutDashboard, Clock, RotateCcw,
  ChevronDown, User
} from "lucide-react"

function elapsed(created_at) {
  if (!created_at) return "just now"
  const s = Math.floor((Date.now() - new Date(created_at)) / 1000)
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return `${Math.floor(s / 3600)}h ago`
}

export default function Sidebar({ onNew, currentTaskId, onSelect }) {
  const [tasks, setTasks] = useState([])

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

      {/* Brand / Logo */}
      <div className="h-14 flex items-center px-4 border-b border-sidebar-border shrink-0">
        <div className="flex items-center gap-2">
          {/* Small logo mark */}
          <div className="w-6 h-6 rounded bg-zinc-900 flex items-center justify-center">
            <span className="text-[10px] font-black text-white leading-none">DS</span>
          </div>
          <div className="flex items-center gap-0.5">
            <span className="text-sm font-bold text-foreground tracking-tight">DS</span>
            <span className="text-sm font-bold text-brand tracking-tight">—</span>
            <span className="text-sm font-bold text-foreground tracking-tight">STAR</span>
          </div>
          <ChevronDown className="w-3.5 h-3.5 text-muted-foreground ml-1" />
        </div>
      </div>

      {/* Nav section */}
      <div className="px-3 py-3 shrink-0">
        {/* Active: Analysis */}
        <div className="flex items-center gap-2.5 px-3 py-2 rounded-md bg-accent text-accent-foreground font-semibold text-[14px] cursor-default">
          <LayoutDashboard className="w-4 h-4 shrink-0" />
          Analysis
        </div>
      </div>

      <Separator />

      {/* New analysis button */}
      <div className="px-3 py-3 shrink-0">
        <Button
          onClick={onNew}
          variant="outline"
          className="w-full justify-start gap-2 text-sm h-8 font-medium"
        >
          <Plus className="w-3.5 h-3.5" />
          New Analysis
        </Button>
      </div>

      {/* History */}
      <ScrollArea className="flex-1 px-3 pb-3">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-2 px-1">
          Recent
        </p>

        <div className="flex flex-col gap-0.5">
          {tasks.length === 0 && (
            <p className="text-xs text-muted-foreground px-2 py-3">No analyses yet</p>
          )}
          {tasks.map(task => {
            const active = task.task_id === currentTaskId
            return (
              <button
                key={task.task_id}
                onClick={() => onSelect(task.task_id, task.query)}
                className={`w-full text-left px-3 py-2.5 rounded-md text-sm transition-colors cursor-pointer ${
                  active
                    ? "bg-accent text-accent-foreground font-medium"
                    : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
                }`}
              >
                <p className="line-clamp-2 leading-snug text-[13px] mb-1">{task.query}</p>
                <div className="flex items-center gap-2 text-[10px] text-muted-foreground font-mono">
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                    task.status === "completed" ? "bg-success" :
                    task.status === "running"   ? "bg-info animate-pulse" :
                    task.status === "failed"    ? "bg-danger" : "bg-zinc-400"
                  }`} />
                  <span>{elapsed(task.created_at)}</span>
                  <span>·</span>
                  <span>R{task.rounds_taken || 1}</span>
                </div>
              </button>
            )
          })}
        </div>
      </ScrollArea>

      <Separator />

      {/* User footer — matches CRM screenshot style */}
      <div className="px-3 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-full bg-zinc-900 flex items-center justify-center shrink-0">
            <span className="text-[10px] font-bold text-white">AK</span>
          </div>
          <div>
            <p className="text-xs font-semibold text-foreground leading-none">Azharuddin K.</p>
            <p className="text-[10px] text-muted-foreground mt-0.5">Supervisory Analyst</p>
          </div>
        </div>
        <Button variant="ghost" size="icon-sm" className="text-muted-foreground">
          <User className="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
  )
}
