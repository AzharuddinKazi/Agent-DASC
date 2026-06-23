import { useState, useEffect } from "react"
import { getTask, submitTask } from "../../api"
import Sidebar from "./Sidebar"
import AgentPipeline from "./AgentPipeline"
import ReportPanel from "./ReportPanel"
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from "../ui/sheet"
import { Menu } from "lucide-react"

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

  // Poll task status
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

  // Track elapsed timer
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
      <div className="relative h-[52px] bg-surface-base border-b border-slate-100 flex items-center justify-between px-4 shrink-0 z-40">
        <div className="flex items-center gap-4">
          <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
            <SheetTrigger asChild>
              <button className="text-slate-600 hover:text-slate-900 transition-colors p-1 cursor-pointer">
                <Menu className="w-5 h-5" />
              </button>
            </SheetTrigger>
            <SheetContent side="left" className="w-[288px] p-0 border-none bg-slate-900" showCloseButton={false}>
              <SheetTitle className="sr-only">History Menu</SheetTitle>
              <Sidebar onNew={() => { onNew(); setDrawerOpen(false); }} currentTaskId={activeTaskId} onSelect={handleSelect} />
            </SheetContent>
          </Sheet>
          
          <div className="flex items-center text-[15px] font-semibold text-slate-900 tracking-tight">
            DS<span className="text-crimson-600 mx-[1px]">—</span>STAR
          </div>
          
          <div className="h-4 w-px bg-slate-100" />
          
          <div className="text-[13px] font-semibold text-slate-900 truncate max-w-[500px]">
            {activeQuery}
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Elapsed Timer in Source Code Pro */}
          <div className="font-mono text-slate-600 text-xs tracking-wider">
            {formatTimer(elapsedTime)}
          </div>

          {/* Status Badges */}
          {isRunning && (
            <div className="flex items-center gap-2 px-2.5 py-1 bg-blue-100 text-blue-600 rounded-[4px] text-[11px] font-medium tracking-wide uppercase">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-pulse" />
              Running
            </div>
          )}
          {isComplete && (
            <div className="flex items-center gap-2 px-2.5 py-1 bg-crimson-100 text-crimson-600 rounded-[4px] text-[11px] font-medium tracking-wide uppercase">
              <span className="w-1.5 h-1.5 rounded-full bg-crimson-600" />
              Complete
            </div>
          )}
          {!isRunning && !isComplete && task?.status === "failed" && (
            <div className="flex items-center gap-2 px-2.5 py-1 bg-red-100 text-red-600 rounded-[4px] text-[11px] font-medium tracking-wide uppercase">
              <span className="w-1.5 h-1.5 rounded-full bg-red-600" />
              Failed
            </div>
          )}

          {/* + New Button */}
          <button 
            onClick={onNew} 
            className="px-3 py-1.5 text-xs font-medium text-slate-900 border border-slate-200 rounded-[4px] hover:bg-slate-050 transition-colors cursor-pointer"
          >
            + New
          </button>
        </div>

        {/* Progress line */}
        <div 
          className="absolute bottom-0 left-0 h-[2px] bg-crimson-600 transition-all duration-700 ease-[cubic-bezier(0.4,0,0.2,1)]"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* AGENT TIMELINE STRIP */}
      <div className="h-[52px] bg-surface-base border-b border-slate-100 px-6 flex items-center shrink-0">
        <AgentPipeline currentAgent={task?.current_agent} status={task?.status} roundsTaken={task?.rounds_taken} />
      </div>

      {/* REPORT AREA (Full Width) */}
      <div className="flex-1 overflow-y-auto w-full relative">
        <div className="max-w-5xl mx-auto px-6 py-8">
          <ReportPanel task={task} query={activeQuery} onFollowUp={handleFollowUp} />
        </div>
      </div>
    </div>
  )
}