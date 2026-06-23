import { useEffect, useState } from "react"
import { getTasks } from "../../api"
import { Plus, Shield, Clock, RotateCcw } from "lucide-react"

function elapsed(created_at) {
  if (!created_at) return "0s ago"
  const secs = Math.floor((Date.now() - new Date(created_at).getTime()) / 1000)
  if (secs < 60) return `${secs}s ago`
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`
  return `${Math.floor(secs / 3600)}h ago`
}

const STATUS_DOT = {
  completed: "bg-green-500",
  running: "bg-blue-500 animate-pulse",
  failed: "bg-red-500",
}

export default function Sidebar({ onNew, currentTaskId, onSelect }) {
  const [tasks, setTasks] = useState([])

  useEffect(() => {
    const fetchTasks = async () => {
      try {
        const r = await getTasks()
        setTasks(r.data)
      } catch (err) {
        console.error("Error fetching history tasks:", err)
      }
    }
    fetchTasks()
    const interval = setInterval(fetchTasks, 5000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="flex flex-col h-full bg-slate-900 text-white font-sans overflow-hidden">

      {/* Header */}
      <div className="px-5 pt-6 pb-4 border-b border-slate-800/60">
        <div className="flex items-center gap-2.5 mb-5">
          <div className="w-8 h-8 rounded-lg bg-crimson-600 flex items-center justify-center shadow-card shrink-0">
            <Shield className="w-4.5 h-4.5 text-white" strokeWidth={2.5} />
          </div>
          <div>
            <div className="text-[15px] font-extrabold text-white tracking-tight leading-none">
              DS<span className="text-crimson-500">—</span>STAR
            </div>
            <div className="text-[9px] text-slate-500 uppercase tracking-[0.15em] font-bold mt-0.5">
              Supervisory Intelligence
            </div>
          </div>
        </div>

        <button
          onClick={onNew}
          className="w-full flex items-center justify-center gap-2 text-[12px] font-semibold text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700/60 hover:border-slate-600 rounded-lg py-2.5 transition-all cursor-pointer"
        >
          <Plus className="w-3.5 h-3.5" />
          New Analysis
        </button>
      </div>

      {/* History */}
      <div className="flex-1 overflow-y-auto py-3">
        <div className="px-5 mb-2">
          <span className="text-[9px] font-bold text-slate-600 uppercase tracking-[0.18em]">
            Recent Analyses
          </span>
        </div>

        <div className="flex flex-col gap-0.5 px-2">
          {tasks.length === 0 && (
            <div className="px-3 py-6 text-center text-[12px] text-slate-600">
              No analyses yet
            </div>
          )}
          {tasks.map(task => {
            const isActive = task.task_id === currentTaskId
            return (
              <button
                key={task.task_id}
                onClick={() => onSelect(task.task_id, task.query)}
                className={`w-full text-left px-3 py-3 rounded-lg transition-all cursor-pointer group ${
                  isActive
                    ? "bg-crimson-600/10 border border-crimson-600/20 text-white"
                    : "border border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                }`}
              >
                <div className="flex items-start justify-between gap-2 mb-1.5">
                  <p className="text-[13px] line-clamp-2 leading-snug flex-1 font-medium">
                    {task.query}
                  </p>
                  <span className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${STATUS_DOT[task.status] || "bg-slate-600"}`} />
                </div>
                <div className="flex items-center gap-2 text-[10px] font-mono text-slate-600">
                  <span className="flex items-center gap-1">
                    <Clock className="w-2.5 h-2.5" />
                    {elapsed(task.created_at)}
                  </span>
                  <span>·</span>
                  <span className="flex items-center gap-1">
                    <RotateCcw className="w-2.5 h-2.5" />
                    Round {task.rounds_taken || 1}
                  </span>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* User Footer */}
      <div className="px-4 py-4 border-t border-slate-800/60 bg-slate-900">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-crimson-600 to-crimson-800 flex items-center justify-center text-[11px] font-bold text-white shrink-0 shadow-card">
            AK
          </div>
          <div>
            <div className="text-[13px] font-semibold text-slate-300">Azharuddin K.</div>
            <div className="text-[10px] text-slate-600">Supervisory Analyst</div>
          </div>
        </div>
      </div>

    </div>
  )
}
