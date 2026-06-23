import ReportSections from "./ReportSections.jsx"
import { AlertTriangle, Zap } from "lucide-react"

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

function AgentLabel({ agent }) {
  return (
    <span className="font-mono text-[10px] px-2 py-0.5 rounded-md bg-slate-100 text-slate-500 uppercase tracking-wider font-bold border border-slate-200">
      {agent || "init"}
    </span>
  )
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
        <div className="rounded-xl bg-red-100 border border-red-200 p-6 max-w-2xl mx-auto mt-8 shadow-card">
          <div className="flex items-center gap-2 text-red-700 text-[14px] font-bold mb-3">
            <AlertTriangle className="w-4.5 h-4.5 text-red-600 shrink-0" />
            Analysis Pipeline Failed
          </div>
          <p className="text-[12px] text-red-800 leading-relaxed font-mono whitespace-pre-wrap bg-white/60 p-4 rounded-lg border border-red-200/60">
            {task?.final_result ?? "An unexpected infrastructure error occurred."}
          </p>
        </div>
      ) : (
        /* Loading / running state */
        <div className="flex flex-col items-center justify-center min-h-[380px] gap-8 w-full font-sans">

          {/* Animated orb */}
          <div className="relative flex items-center justify-center">
            <div className="absolute w-20 h-20 rounded-full bg-blue-100 animate-ping opacity-40 duration-[2000ms]" />
            <div className="absolute w-14 h-14 rounded-full bg-blue-100 animate-ping opacity-60 duration-[1500ms] delay-200" />
            <div className="relative z-10 w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center shadow-[0_0_20px_rgba(37,99,235,0.4),0_0_40px_rgba(37,99,235,0.2)]">
              <Zap className="w-5 h-5 text-white" strokeWidth={2.5} />
            </div>
          </div>

          <div className="flex flex-col items-center text-center gap-3">
            <AgentLabel agent={baseAgent} />
            <p className="text-[15px] text-slate-700 font-semibold leading-snug max-w-sm">
              {getAgentDescription(rawAgent)}
            </p>
            <p className="text-[12px] text-slate-400 max-w-xs leading-relaxed">
              The autonomous pipeline is working through your query. This typically takes 30–90 seconds.
            </p>
          </div>

          {/* Subtle progress dots */}
          <div className="flex items-center gap-1.5">
            {[0, 1, 2].map(i => (
              <span
                key={i}
                className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce"
                style={{ animationDelay: `${i * 0.15}s` }}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
