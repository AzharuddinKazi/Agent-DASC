import { useEffect, useState } from "react"
import { getTasks } from "../../api"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Plus, Shield, Clock, RotateCcw } from "lucide-react"

function elapsed(created_at) {
  if (!created_at) return "0s ago"
  const s = Math.floor((Date.now() - new Date(created_at)) / 1000)
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return `${Math.floor(s / 3600)}h ago`
}

export default function Sidebar({ onNew, currentTaskId, onSelect }) {
  const [tasks, setTasks] = useState([])

  useEffect(() => {
    const fetch = async () => {
      try { const r = await getTasks(); setTasks(r.data) }
      catch (e) { console.error(e) }
    }
    fetch()
    const t = setInterval(fetch, 5000)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="flex flex-col h-full bg-sidebar text-sidebar-foreground font-sans">

      {/* Header */}
      <div className="px-5 pt-6 pb-4">
        <div className="flex items-center gap-2.5 mb-5">
          <div className="w-8 h-8 rounded-lg bg-sidebar-primary flex items-center justify-center shrink-0">
            <Shield className="w-4 h-4 text-sidebar-primary-foreground" strokeWidth={2.5} />
          </div>
          <div>
            <div className="text-[15px] font-extrabold tracking-tight leading-none">
              DS<span className="text-sidebar-primary">—</span>STAR
            </div>
            <div className="text-[9px] text-sidebar-foreground/40 uppercase tracking-[0.15em] font-bold mt-0.5">
              Supervisory Intelligence
            </div>
          </div>
        </div>

        <Button
          onClick={onNew}
          variant="outline"
          className="w-full gap-2 border-sidebar-border bg-transparent text-sidebar-foreground/60 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground hover:border-sidebar-accent"
        >
          <Plus className="w-3.5 h-3.5" />
          New Analysis
        </Button>
      </div>

      <Separator className="bg-sidebar-border" />

      {/* History list */}
      <ScrollArea className="flex-1 py-3">
        <p className="px-5 mb-2 text-[9px] font-bold uppercase tracking-[0.18em] text-sidebar-foreground/30">
          Recent Analyses
        </p>

        <div className="flex flex-col gap-0.5 px-2">
          {tasks.length === 0 && (
            <p className="px-3 py-6 text-center text-xs text-sidebar-foreground/30">No analyses yet</p>
          )}
          {tasks.map(task => {
            const active = task.task_id === currentTaskId
            return (
              <button
                key={task.task_id}
                onClick={() => onSelect(task.task_id, task.query)}
                className={`w-full text-left px-3 py-3 rounded-lg transition-all cursor-pointer ${
                  active
                    ? "bg-sidebar-primary/10 border border-sidebar-primary/25 text-sidebar-foreground"
                    : "border border-transparent text-sidebar-foreground/50 hover:text-sidebar-foreground hover:bg-sidebar-accent/50"
                }`}
              >
                <div className="flex items-start justify-between gap-2 mb-1.5">
                  <p className="text-[13px] line-clamp-2 leading-snug flex-1 font-medium">{task.query}</p>
                  <span className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${
                    task.status === "completed" ? "bg-green-500" :
                    task.status === "running"   ? "bg-blue-500 animate-pulse" :
                    task.status === "failed"    ? "bg-red-500" : "bg-sidebar-foreground/30"
                  }`} />
                </div>
                <div className="flex items-center gap-2 text-[10px] font-mono text-sidebar-foreground/30">
                  <span className="flex items-center gap-1"><Clock className="w-2.5 h-2.5" />{elapsed(task.created_at)}</span>
                  <span>·</span>
                  <span className="flex items-center gap-1"><RotateCcw className="w-2.5 h-2.5" />Round {task.rounds_taken || 1}</span>
                </div>
              </button>
            )
          })}
        </div>
      </ScrollArea>

      <Separator className="bg-sidebar-border" />

      {/* Footer */}
      <div className="px-4 py-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-sidebar-primary flex items-center justify-center text-[11px] font-bold text-sidebar-primary-foreground shrink-0">
            AK
          </div>
          <div>
            <p className="text-[13px] font-semibold text-sidebar-foreground">Azharuddin K.</p>
            <p className="text-[10px] text-sidebar-foreground/40">Supervisory Analyst</p>
          </div>
        </div>
      </div>
    </div>
  )
}
