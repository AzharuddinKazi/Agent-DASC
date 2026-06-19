import { useEffect, useState } from "react"
import { getTasks } from "@/api"

const STATUS_DOT = {
  completed: "bg-green-500",
  running:   "bg-yellow-400 animate-pulse",
  failed:    "bg-red-500",
}

function elapsed(created_at) {
  const secs = Math.floor((Date.now() - new Date(created_at)) / 1000)
  if (secs < 60)   return `${secs}s ago`
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`
  return `${Math.floor(secs / 3600)}h ago`
}

export default function Sidebar({ onNew, currentTaskId, onSelect }) {
  const [tasks, setTasks] = useState([])

  useEffect(() => {
    const fetch = async () => {
      try { const r = await getTasks(); setTasks(r.data) } catch {}
    }
    fetch()
    const interval = setInterval(fetch, 5000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="flex flex-col h-full bg-[#09090B] border-r border-zinc-800/60">
      <div className="p-4 border-b border-zinc-800/60">
        <div className="text-sm font-medium text-zinc-100">DS—STAR</div>
        <div className="text-xs text-zinc-600 mt-0.5">Powered by AI agents</div>
      </div>

      <div className="p-3">
        <button
          onClick={onNew}
          className="w-full flex items-center gap-2 text-xs font-medium text-violet-400 bg-violet-950/40 border border-violet-800/30 rounded-lg px-3 py-2 hover:bg-violet-950/60 transition-colors"
        >
          <i className="ti ti-plus text-sm" />
          New analysis
        </button>
      </div>

      <div className="px-3 pb-2">
        <div className="text-xs font-medium text-zinc-700 uppercase tracking-widest px-1 mb-2">
          Recent
        </div>
        <div className="flex flex-col gap-0.5 overflow-y-auto max-h-[460px]">
          {tasks.length === 0 && (
            <p className="text-xs text-zinc-700 px-1 py-3 text-center">No tasks yet</p>
          )}
          {tasks.map(task => (
            <button
              key={task.task_id}
              onClick={() => onSelect(task.task_id, task.query)}
              className={`w-full text-left px-2 py-2 rounded-lg transition-colors group ${
                task.task_id === currentTaskId
                  ? "bg-zinc-800/60 border-l-2 border-violet-500"
                  : "hover:bg-zinc-900"
              }`}
            >
              <div className="flex items-start justify-between gap-2 mb-1">
                <p className="text-xs text-zinc-400 line-clamp-2 leading-relaxed flex-1">
                  {task.query}
                </p>
                <span className={`w-1.5 h-1.5 rounded-full mt-1 flex-shrink-0 ${STATUS_DOT[task.status] ?? "bg-zinc-600"}`} />
              </div>
              <p className="text-xs text-zinc-700">{elapsed(task.created_at)}</p>
            </button>
          ))}
        </div>
      </div>

      <div className="mt-auto p-4 border-t border-zinc-800/60">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-violet-900/50 flex items-center justify-center text-xs font-medium text-violet-400">
            AK
          </div>
          <span className="text-xs text-zinc-600">Azharuddin K.</span>
        </div>
      </div>
    </div>
  )
}