import { useEffect, useState } from "react"
import { getTasks } from "../../api"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { ScrollArea } from "@/components/ui/scroll-area"
import { MessageSquare, LayoutGrid, User, Settings } from "lucide-react"

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

      {/* Brand / Logo — click to return home */}
      <button
        onClick={onNew}
        className="h-14 flex items-center px-4 border-b border-sidebar-border shrink-0 cursor-pointer hover:bg-accent/60 transition-colors text-left"
      >
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-zinc-900 flex items-center justify-center shrink-0">
            <span className="text-[11px] font-black text-white leading-none">FIP</span>
          </div>
          <div className="min-w-0">
            <p className="text-sm font-bold text-foreground tracking-tight leading-none">FIP</p>
            <p className="text-[10px] text-muted-foreground mt-0.5 truncate">Financial Intelligence Platform</p>
          </div>
        </div>
      </button>

      {/* Nav section */}
      <div className="px-3 py-3 shrink-0 flex flex-col gap-0.5">
        <button
          onClick={onNew}
          className="flex items-center gap-2.5 px-3 py-2 rounded-md bg-accent text-accent-foreground font-semibold text-[14px] cursor-pointer"
        >
          <MessageSquare className="w-4 h-4 shrink-0" />
          New Analysis
        </button>
        <button
          disabled
          className="flex items-center gap-2.5 px-3 py-2 rounded-md text-muted-foreground/60 font-medium text-[14px] cursor-not-allowed"
          title="Coming soon"
        >
          <LayoutGrid className="w-4 h-4 shrink-0" />
          Dashboard
        </button>
      </div>

      <Separator />

      {/* History */}
      <ScrollArea className="flex-1 min-h-0 px-3 pt-3 pb-3">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-2 px-1">
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
                  <p className="line-clamp-2 leading-snug text-[13px] mb-1 flex-1">{task.query}</p>
                  <span className={`shrink-0 w-4 h-4 rounded flex items-center justify-center text-[9px] font-bold ${
                    isReport ? "bg-purple-100 text-purple-700" : "bg-blue-100 text-blue-700"
                  }`}>
                    {isReport ? "R" : "I"}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[10px] text-muted-foreground font-mono">
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                    task.status === "completed" ? "bg-success" :
                    task.status === "running"   ? "bg-info animate-pulse" :
                    task.status === "failed"    ? "bg-danger" : "bg-zinc-400"
                  }`} />
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
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-full bg-zinc-900 flex items-center justify-center shrink-0">
            <span className="text-[10px] font-bold text-white">AK</span>
          </div>
          <div>
            <p className="text-xs font-semibold text-foreground leading-none">Azharuddin Kazi</p>
            <p className="text-[10px] text-muted-foreground mt-0.5">Fraud Prevention</p>
          </div>
        </div>
        <Button variant="ghost" size="icon-sm" className="text-muted-foreground">
          <Settings className="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
  )
}
