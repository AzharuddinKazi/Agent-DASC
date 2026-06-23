import { useEffect, useState } from "react"
import { getTasks } from "../../api"
import { Plus } from "lucide-react"

function elapsed(created_at) {
  if (!created_at) return "0s ago"
  const secs = Math.floor((Date.now() - new Date(created_at).getTime()) / 1000)
  if (secs < 60)   return `${secs}s ago`
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`
  return `${Math.floor(secs / 3600)}h ago`
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
    <div className="flex flex-col h-full bg-slate-900 text-white font-sans">
      
      {/* Header */}
      <div className="p-6 pb-4 flex flex-col gap-4">
        <div>
          <div className="text-[16px] font-semibold text-white tracking-tight mb-1">
            DS<span className="text-crimson-600 mx-[1px]">—</span>STAR
          </div>
          <div className="text-[9px] text-slate-400 uppercase tracking-widest font-bold">
            Supervisory Intelligence
          </div>
        </div>
        
        {/* + New Ghost Button in slate-400 */}
        <button
          onClick={onNew}
          className="w-full flex items-center justify-center gap-1.5 text-xs font-medium text-slate-400 border border-slate-800 bg-transparent rounded-[4px] py-2 hover:bg-slate-800 hover:text-slate-200 transition-colors cursor-pointer"
        >
          <Plus className="w-3.5 h-3.5" />
          + New analysis
        </button>
      </div>

      {/* History Items Section */}
      <div className="flex-1 overflow-y-auto">
        <div className="text-[9px] font-bold text-slate-600 uppercase tracking-widest px-6 mb-2">
          History
        </div>
        
        <div className="flex flex-col">
          {tasks.map(task => {
            const isActive = task.task_id === currentTaskId
            return (
              <button
                key={task.task_id}
                onClick={() => onSelect(task.task_id, task.query)}
                className={`w-full text-left px-6 py-3 transition-all cursor-pointer ${
                  isActive 
                    ? "bg-crimson-100/5 border-l-2 border-l-crimson-600 text-slate-200" 
                    : "bg-transparent border-l-2 border-transparent text-slate-600 hover:text-slate-200 hover:bg-slate-800/30"
                }`}
              >
                <div className="flex items-start justify-between gap-3 mb-1.5">
                  <p className="text-[13px] line-clamp-2 leading-snug flex-1">
                    {task.query}
                  </p>
                  <span className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${
                    task.status === 'completed' ? 'bg-green-600' :
                    task.status === 'running'   ? 'bg-blue-600 animate-pulse' : 
                    task.status === 'failed'    ? 'bg-red-600' : 'bg-slate-600'
                  }`} />
                </div>
                
                {/* Metadata row: elapsed + round count in slate-600 9px Source Code Pro */}
                <div className="flex items-center gap-2 text-[9px] font-mono text-slate-600">
                  <span>{elapsed(task.created_at)}</span>
                  <span>·</span>
                  <span>Round {task.rounds_taken || 1}</span>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-slate-800 bg-slate-900 mt-auto">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full border border-crimson-600 bg-slate-700 flex items-center justify-center text-[10px] font-semibold text-white">
            AK
          </div>
          <span className="text-[13px] text-slate-400 font-medium">Azharuddin K.</span>
        </div>
      </div>

    </div>
  )
}