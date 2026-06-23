import { useState, useEffect } from "react"
import { getTask, submitTask } from "../../api"
import Sidebar from "./Sidebar"
import AgentPipeline from "./AgentPipeline"
import ReportPanel from "./ReportPanel"
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Menu, Shield } from "lucide-react"

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

  const formatTimer = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden font-sans">

      {/* TOP BAR */}
      <div className="relative h-[54px] bg-card border-b border-border flex items-center justify-between px-3 shrink-0 z-40">
        <div className="flex items-center gap-2 min-w-0">
          {/* Hamburger */}
          <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="shrink-0">
                <Menu className="w-4 h-4" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-[280px] p-0 border-none bg-sidebar" showCloseButton={false}>
              <SheetTitle className="sr-only">History</SheetTitle>
              <Sidebar onNew={() => { onNew(); setDrawerOpen(false) }} currentTaskId={activeTaskId} onSelect={handleSelect} />
            </SheetContent>
          </Sheet>

          {/* Logo */}
          <div className="flex items-center gap-2 shrink-0">
            <div className="w-6 h-6 rounded-md bg-primary flex items-center justify-center">
              <Shield className="w-3.5 h-3.5 text-primary-foreground" strokeWidth={2.5} />
            </div>
            <span className="text-[15px] font-extrabold text-foreground tracking-tight">
              DS<span className="text-primary">—</span>STAR
            </span>
          </div>

          <Separator orientation="vertical" className="h-5 mx-1" />

          <span className="text-sm font-semibold text-foreground truncate">
            {activeQuery}
          </span>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {/* Timer */}
          <span className="font-mono text-xs text-muted-foreground tabular-nums tracking-wider">
            {formatTimer(elapsedTime)}
          </span>

          {/* Status badge */}
          {isRunning  && <Badge variant="outline" className="gap-1.5 border-blue-200 bg-blue-050 text-blue-700"><span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />Running</Badge>}
          {isComplete && <Badge variant="outline" className="gap-1.5 border-green-200 bg-green-050 text-green-700"><span className="w-1.5 h-1.5 rounded-full bg-green-500" />Complete</Badge>}
          {isFailed   && <Badge variant="destructive" className="gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-destructive-foreground" />Failed</Badge>}

          <Button variant="outline" size="sm" onClick={onNew} className="text-xs">
            + New
          </Button>
        </div>

        {/* Progress bar */}
        <div
          className="absolute bottom-0 left-0 h-[2px] transition-all duration-700 ease-in-out"
          style={{
            width: `${progress}%`,
            background: isComplete ? '#16A34A' : isFailed ? '#DC2626' : 'linear-gradient(90deg,#C81D25,#F05050)'
          }}
        />
      </div>

      {/* PIPELINE STRIP */}
      <div className="h-[52px] bg-card border-b border-border px-6 flex items-center shrink-0">
        <AgentPipeline currentAgent={task?.current_agent} status={task?.status} roundsTaken={task?.rounds_taken} />
      </div>

      {/* REPORT AREA */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto px-6 py-8">
          <ReportPanel task={task} query={activeQuery} onFollowUp={handleFollowUp} />
        </div>
      </div>
    </div>
  )
}
