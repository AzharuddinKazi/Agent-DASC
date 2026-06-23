import { useState, useEffect } from "react"
import { getTask, submitTask } from "../../api"
import Sidebar from "./Sidebar"
import AgentPipeline from "./AgentPipeline"
import ReportPanel from "./ReportPanel"
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Menu } from "lucide-react"

const PROGRESS_BY_AGENT = {
  analyzer: 10, planner: 25, coder: 40, executor: 55,
  debugger: 60, verifier: 72, router: 82, finalizer: 92,
}

export default function Dashboard({ query, taskId, onNew }) {
  const [task, setTask] = useState(null)
  const [activeQuery, setActiveQuery] = useState(query)
  const [activeTaskId, setActiveTaskId] = useState(taskId)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [elapsedTime, setElapsedTime] = useState(0)

  useEffect(() => {
    if (!activeTaskId) return
    setTask(null)
    const poll = async () => {
      try {
        const r = await getTask(activeTaskId)
        setTask(r.data)
        if (r.data.status !== "running") clearInterval(interval)
      } catch (err) { console.error(err) }
    }
    poll()
    const interval = setInterval(poll, 2000)
    return () => clearInterval(interval)
  }, [activeTaskId])

  useEffect(() => {
    if (!task) return
    if (task.status === "running") {
      const start = new Date(task.created_at || Date.now()).getTime()
      const update = () => setElapsedTime(Math.max(0, Math.floor((Date.now() - start) / 1000)))
      update()
      const t = setInterval(update, 1000)
      return () => clearInterval(t)
    } else if (task.created_at && task.updated_at) {
      setElapsedTime(Math.max(0, Math.floor((new Date(task.updated_at) - new Date(task.created_at)) / 1000)))
    }
  }, [task])

  const handleSelect = (id, q) => { setActiveTaskId(id); setActiveQuery(q); setDrawerOpen(false) }
  const handleFollowUp = async (text) => {
    if (!text.trim()) return
    try {
      const res = await submitTask(text)
      setActiveTaskId(res.data.task_id); setActiveQuery(text); setTask(null); setElapsedTime(0)
    } catch (err) { console.error(err) }
  }

  const isRunning  = task?.status === "running"
  const isComplete = task?.status === "completed"
  const isFailed   = task?.status === "failed"

  const baseAgent = task?.current_agent?.startsWith("planner") ? "planner" : task?.current_agent
  const progress  = isComplete ? 100 : isFailed ? 100 : PROGRESS_BY_AGENT[baseAgent] ?? 5

  const formatTimer = (s) =>
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`

  return (
    <div className="h-screen flex bg-background overflow-hidden font-sans">

      {/* ── Permanent sidebar (desktop) ── */}
      <div className="hidden md:flex w-[240px] shrink-0 border-r border-border flex-col bg-sidebar">
        <Sidebar
          onNew={onNew}
          currentTaskId={activeTaskId}
          onSelect={handleSelect}
        />
      </div>

      {/* ── Main column ── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">

        {/* TOP BAR */}
        <div className="relative h-14 border-b border-border bg-card flex items-center justify-between px-4 shrink-0 z-40">
          <div className="flex items-center gap-3 min-w-0">
            {/* Mobile hamburger */}
            <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="md:hidden shrink-0">
                  <Menu className="w-4 h-4" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-[240px] p-0 border-r border-border bg-sidebar" showCloseButton={false}>
                <SheetTitle className="sr-only">Navigation</SheetTitle>
                <Sidebar onNew={() => { onNew(); setDrawerOpen(false) }} currentTaskId={activeTaskId} onSelect={handleSelect} />
              </SheetContent>
            </Sheet>

            {/* Page title */}
            <div>
              <h1 className="text-[15px] font-bold text-foreground leading-none">Analysis Dashboard</h1>
              <p className="text-[13px] text-muted-foreground mt-0.5 truncate max-w-[420px]">{activeQuery}</p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <span className="font-mono text-[13px] text-muted-foreground tabular-nums">
              {formatTimer(elapsedTime)}
            </span>

            {isRunning  && <Badge variant="outline" className="gap-1.5 text-info border-info/30 bg-info-bg text-[12px]"><span className="w-1.5 h-1.5 rounded-full bg-info animate-pulse" />Running</Badge>}
            {isComplete && <Badge variant="outline" className="gap-1.5 text-success border-success/30 bg-success-bg text-[12px]"><span className="w-1.5 h-1.5 rounded-full bg-success" />Complete</Badge>}
            {isFailed   && <Badge variant="destructive" className="gap-1.5 text-[12px]"><span className="w-1.5 h-1.5 rounded-full bg-white/80" />Failed</Badge>}

            <Button size="sm" onClick={onNew} className="h-8 text-[13px] px-4">
              + New Analysis
            </Button>
          </div>

          {/* Progress bar */}
          <div
            className="absolute bottom-0 left-0 h-[2px] transition-all duration-700 ease-in-out"
            style={{
              width: `${progress}%`,
              background: isComplete ? '#16a34a' : isFailed ? '#dc2626' : '#18181b'
            }}
          />
        </div>

        {/* AGENT PIPELINE */}
        <div className="h-12 border-b border-border bg-zinc-050 px-6 flex items-center shrink-0">
          <AgentPipeline
            currentAgent={task?.current_agent}
            status={task?.status}
            roundsTaken={task?.rounds_taken}
          />
        </div>

        {/* REPORT AREA */}
        <div className="flex-1 overflow-y-auto bg-background">
          <div className="max-w-7xl mx-auto px-6 py-6">
            <ReportPanel task={task} query={activeQuery} onFollowUp={handleFollowUp} />
          </div>
        </div>
      </div>
    </div>
  )
}
