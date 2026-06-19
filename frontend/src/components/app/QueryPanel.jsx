import AgentPipeline from "./AgentPipeline"
import StatusMessage from "./StatusMessage"

export default function QueryPanel({ query, task }) {
  return (
    <div className="flex flex-col h-full overflow-hidden border-r border-zinc-800/60">
      <div className="p-6 border-b border-zinc-800/60">
        <div className="text-xs font-medium text-zinc-600 uppercase tracking-widest mb-2">
          Query
        </div>
        <p className="text-sm font-medium text-zinc-200 leading-relaxed mb-4">{query}</p>
        <StatusMessage
          currentAgent={task?.current_agent}
          status={task?.status}
          rounds={task?.rounds_taken}
        />
      </div>

      <div className="p-6 border-b border-zinc-800/60">
        <div className="text-xs font-medium text-zinc-600 uppercase tracking-widest mb-5">
          Agent pipeline
        </div>
        <AgentPipeline
          currentAgent={task?.current_agent}
          status={task?.status}
        />
      </div>

      <div className="p-6 flex-1 overflow-y-auto">
        <div className="text-xs font-medium text-zinc-600 uppercase tracking-widest mb-4">
          Task info
        </div>
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-zinc-600">Status</span>
            <span className={`text-xs font-medium ${
              task?.status === "completed" ? "text-green-400" :
              task?.status === "failed"    ? "text-red-400" :
                                            "text-violet-400"
            }`}>{task?.status ?? "—"}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-zinc-600">Rounds</span>
            <span className="text-xs text-zinc-400 font-mono">{task?.rounds_taken ?? "—"}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-zinc-600">Task ID</span>
            <span className="text-xs text-zinc-600 font-mono">{task?.task_id?.slice(0, 8)}...</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-zinc-600">Started</span>
            <span className="text-xs text-zinc-600">
              {task?.created_at ? new Date(task.created_at).toLocaleTimeString() : "—"}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}