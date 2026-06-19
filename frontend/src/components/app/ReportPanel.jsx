import ReportSections from "./ReportSections"

const PROGRESS_BY_AGENT = {
  analyzer: 10, planner: 25, coder: 40,
  executor: 55, verifier: 70, router: 75, finalizer: 90,
}

export default function ReportPanel({ task, query }) {
  const base = task?.current_agent?.startsWith("planner") ? "planner" : task?.current_agent
  const progress = task?.status === "completed" ? 100
    : task?.status === "failed" ? 100
    : PROGRESS_BY_AGENT[base] ?? 5

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="px-6 py-4 border-b border-zinc-800/60 flex items-center justify-between">
        <div className="text-xs font-medium text-zinc-600 uppercase tracking-widest">
          Live analysis · report
        </div>
        {task?.status === "running" && (
          <div className="flex items-center gap-2 text-xs text-violet-400">
            <div className="w-1.5 h-1.5 rounded-full bg-violet-500 animate-pulse" />
            Generating · {progress}%
          </div>
        )}
        {task?.status === "completed" && (
          <div className="flex items-center gap-2 text-xs text-green-400">
            <i className="ti ti-circle-check text-sm" />
            Complete
          </div>
        )}
      </div>

      <div className="h-0.5 bg-zinc-800">
        <div
          className="h-0.5 bg-violet-600 transition-all duration-700"
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {task?.status === "completed" && task?.final_result ? (
          <ReportSections result={task.final_result} query={query} script={task.current_script} />
        ) : task?.status === "failed" ? (
          <div className="rounded-xl bg-red-950/30 border border-red-900/50 p-4">
            <div className="flex items-center gap-2 text-red-400 text-sm font-medium mb-2">
              <i className="ti ti-alert-circle" />
              Analysis failed
            </div>
            <p className="text-xs text-red-400/70 leading-relaxed">
              {task?.final_result ?? "An unexpected error occurred."}
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
            <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center">
              <i className="ti ti-report text-zinc-600 text-lg" />
            </div>
            <p className="text-xs text-zinc-600 leading-relaxed">
              Report will appear here<br />as agents complete their work
            </p>
          </div>
        )}
      </div>
    </div>
  )
}