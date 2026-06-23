import { useState, useEffect } from "react"
import { getTask, submitTask } from "../../api"
import Sidebar from "./Sidebar"
import AgentPipeline from "./AgentPipeline"
import ReportPanel from "./ReportPanel"
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from "../ui/sheet"
import { Menu, Shield } from "lucide-react"

const PROGRESS_BY_AGENT = {
  analyzer: 10,
  planner: 25,
  coder: 40,
  executor: 55,
  debugger: 60,
  verifier: 72,
  router: 82,
  finalizer: 92,
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
      } catch (err) {
        console.error("Error polling task:", err)
      }
    }
    poll()
    const interval = setInterval(poll, 2000)
    return () => clearInterval(interval)
  }, [activeTaskId])

  useEffect(() => {
    if (!task) return
    if (task.status === "running") {
      const start = new Date(task.created_at || Date.now()).getTime()
      const update = () => {
        setElapsedTime(Math.max(0, Math.floor((Date.now() - start) / 1000)))
      }
      update()
      const timer = setInterval(update, 1000)
      return () => clearInterval(timer)
    } else {
      if (task.created_at && task.updated_at) {
        const diff = Math.max(0, Math.floor((new Date(task.updated_at).getTime() - new Date(task.created_at).getTime()) / 1000))
        setElapsedTime(diff)
      }
    }
  }, [task])

  const handleSelect = (id, q) => {
    setActiveTaskId(id)
    setActiveQuery(q)
    setDrawerOpen(false)
  }

  const handleFollowUp = async (text) => {
    if (!text.trim()) return
    try {
      const res = await submitTask(text)
      setActiveTaskId(res.data.task_id)
      setActiveQuery(text)
      setTask(null)
      setElapsedTime(0)
    } catch (err) {
      console.error("Error submitting follow-up:", err)
    }
  }

  const isRunning = task?.status === "running"
  const isComplete = task?.status === "completed"

  const baseAgent = task?.current_agent?.startsWith("planner") ? "planner" : task?.current_agent
  const progress = isComplete ? 100 : task?.status === "failed" ? 100 : PROGRESS_BY_AGENT[baseAgent] ?? 5

  const formatTimer = (totalSeconds) => {
    const mins = Math.floor(totalSeconds / 60)
    const secs = totalSeconds % 60
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`
  }

  return (
    <div className="h-screen flex flex-col bg-surface-subtle overflow-hidden font-sans">

      {/* TOP BAR */}
      <div className="relative h-[54px] bg-surface-base border-b border-slate-100 flex items-center justify-between px-4 shrink-0 z-40 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
        <div className="flex items-center gap-3 min-w-0">
          <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
            <SheetTrigger asChild>
              <button className="w-8 h-8 rounded-md flex items-center justify-center text-slate-500 hover:text-slate-900 hover:bg-slate-050 transition-all cursor-pointer shrink-0">
                <Menu className="w-4.5 h-4.5" />
              </button>
            </SheetTrigger>
            <SheetContent side="left" className="w-[288px] p-0 border-none bg-slate-900" showCloseButton={false}>
              <SheetTitle className="sr-only">History Menu</SheetTitle>
              <Sidebar onNew={() => { onNew(); setDrawerOpen(false) }} currentTaskId={activeTaskId} onSelect={handleSelect} />
            </SheetContent>
          </Sheet>

          {/* Logo */}
          <div className="flex items-center gap-2 shrink-0">
            <div className="w-6 h-6 rounded-md bg-crimson-600 flex items-center justify-center">
              <Shield className="w-3.5 h-3.5 text-white" strokeWidth={2.5} />
            </div>
            <div className="text-[15px] font-extrabold text-slate-900 tracking-tight leading-none">
              DS<span className="text-crimson-600">—</span>STAR
            </div>
          </div>

          <div className="w-px h-5 bg-slate-200 shrink-0" />

          {/* Query */}
          <div className="text-[13px] font-semibold text-slate-700 truncate min-w-0">
            {activeQuery}
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          {/* Timer */}
          <div className="font-mono text-[12px] text-slate-400 tracking-wider tabular-nums">
            {formatTimer(elapsedTime)}
          </div>

          {/* Status Badge */}
          {isRunning && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 bg-blue-050 text-blue-600 border border-blue-100 rounded-md text-[11px] font-semibold tracking-wide uppercase">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
              Running
            </div>
          )}
          {isComplete && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 bg-green-050 text-green-700 border border-green-100 rounded-md text-[11px] font-semibold tracking-wide uppercase">
              <span className="w-1.5 h-1.5 rounded-full bg-green-600" />
              Complete
            </div>
          )}
          {!isRunning && !isComplete && task?.status === "failed" && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 bg-red-100 text-red-600 border border-red-200 rounded-md text-[11px] font-semibold tracking-wide uppercase">
              <span className="w-1.5 h-1.5 rounded-full bg-red-600" />
              Failed
            </div>
          )}

          {/* New Analysis button */}
          <button
            onClick={onNew}
            className="px-3 py-1.5 text-[12px] font-semibold text-slate-600 border border-slate-200 rounded-md hover:bg-slate-050 hover:text-slate-900 hover:border-slate-300 transition-all cursor-pointer"
          >
            + New
          </button>
        </div>

        {/* Progress bar */}
        <div
          className="absolute bottom-0 left-0 h-[2px] transition-all duration-700 ease-[cubic-bezier(0.4,0,0.2,1)]"
          style={{
            width: `${progress}%`,
            background: isComplete
              ? 'linear-gradient(90deg, #16A34A, #22c55e)'
              : task?.status === "failed"
              ? '#DC2626'
              : 'linear-gradient(90deg, #C81D25, #E02020, #F05050)'
          }}
        />
      </div>

      {/* AGENT PIPELINE STRIP */}
      <div className="h-[56px] bg-surface-base border-b border-slate-100 px-8 flex items-center shrink-0 shadow-[0_1px_2px_rgba(0,0,0,0.03)]">
        <AgentPipeline currentAgent={task?.current_agent} status={task?.status} roundsTaken={task?.rounds_taken} />
      </div>

      {/* REPORT AREA */}
      <div className="flex-1 overflow-y-auto w-full relative">
        <div className="max-w-5xl mx-auto px-6 py-8">
          <ReportPanel task={task} query={activeQuery} onFollowUp={handleFollowUp} />
        </div>
      </div>
    </div>
  )
}
