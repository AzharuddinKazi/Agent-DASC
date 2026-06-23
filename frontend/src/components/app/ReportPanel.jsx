import ReportSections from "./ReportSections.jsx"
import { AlertTriangle } from "lucide-react"

// Helper to translate raw agent strings into analyst-friendly descriptions
function getAgentDescription(agent) {
  if (!agent) return "Initializing autonomous pipeline..."
  if (agent.startsWith("planner")) {
    const match = agent.match(/\d+/)
    const round = match ? match[0] : ""
    return round ? `Formulating logical plan for iteration ${round}...` : "Formulating analytical plan..."
  }
  
  const descriptions = {
    analyzer: "Analyzing dataset schemas and preparing context...",
    coder: "Translating plan into secure Pandas execution script...",
    executor: "Spinning up isolated Docker sandbox and executing code...",
    verifier: "Evaluating execution results against your original query...",
    router: "Determining if further analysis is required...",
    debugger: "Execution failed. Analyzing traceback and writing code patch...",
    finalizer: "Formatting final report and data tables..."
  }
  
  return descriptions[agent] || `Agent active: ${agent}`
}

export default function ReportPanel({ task, query, onFollowUp }) {
  const rawAgent = task?.current_agent
  const baseAgent = rawAgent?.startsWith("planner") ? "planner" : rawAgent

  return (
    <div className="w-full">
      {task?.status === "completed" && task?.final_result ? (
        <ReportSections 
          result={task.final_result} 
          query={query} 
          script={task.current_script} 
          plan={task.cumulative_plan} 
          taskId={task.task_id}
          onFollowUp={onFollowUp}
        />
      ) : task?.status === "failed" ? (
        <div className="rounded-[4px] bg-red-100 border border-red-200 p-5 max-w-2xl mx-auto mt-6 shadow-sm font-sans">
          <div className="flex items-center gap-2 text-red-700 text-[13px] font-semibold mb-3">
            <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
            Analysis Pipeline Failed
          </div>
          <p className="text-xs text-red-800 leading-relaxed font-mono whitespace-pre-wrap bg-white/50 p-3 rounded border border-red-500/10">
            {task?.final_result ?? "An unexpected infrastructure error occurred."}
          </p>
        </div>
      ) : (
        /* --- Redesigned Light Neutral Pulsing UI --- */
        <div className="flex flex-col items-center justify-center min-h-[350px] gap-6 w-full font-sans">
          <div className="relative flex items-center justify-center w-14 h-14 rounded-full bg-blue-100 border border-blue-200">
            <div className="absolute inset-0 rounded-full animate-ping bg-blue-600/10 duration-1000"></div>
            <div className="relative z-10 w-3.5 h-3.5 rounded-full bg-blue-600 shadow-[0_0_12px_rgba(37,99,235,0.4)]"></div>
          </div>

          <div className="text-center space-y-2">
            <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
              {baseAgent || "System Initialization"}
            </h3>
            <p className="text-sm text-slate-600 leading-relaxed max-w-sm animate-pulse font-medium">
              {getAgentDescription(rawAgent)}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}