import { Tooltip, TooltipContent, TooltipTrigger } from "../ui/tooltip"
import { Check, Search, ListTodo, Code, Play, ShieldCheck, GitBranch, Sparkles, AlertCircle } from "lucide-react"

const AGENT_ORDER = ["analyzer", "planner", "coder", "executor", "verifier", "router", "finalizer"]

const AGENT_DESCRIPTIONS = {
  analyzer: "Profiles schema, row count, and column types",
  planner: "Maps the query to a step-by-step analysis plan",
  coder: "Writes Python to execute the plan",
  executor: "Runs the script in an isolated sandbox",
  verifier: "Checks result completeness and factual accuracy",
  router: "Decides whether to refine or finalise",
  finalizer: "Structures the result into a clean report",
}

const AGENT_MESSAGES = {
  analyzer: "Profiling your data files...",
  planner: "Planning the analysis approach...",
  coder: "Writing analysis code...",
  executor: "Running the analysis...",
  verifier: "Checking result quality...",
  router: "Refining the approach, starting next round...",
  finalizer: "Preparing your report...",
}

const AGENT_ICONS = {
  analyzer: Search,
  planner: ListTodo,
  coder: Code,
  executor: Play,
  verifier: ShieldCheck,
  router: GitBranch,
  finalizer: Sparkles,
}

function getStepState(agent, currentAgent, status) {
  if (status === "completed") return "done"
  if (!currentAgent) return "pending"
  const currentBase = currentAgent.startsWith("planner") ? "planner" : currentAgent
  const currentIdx = AGENT_ORDER.indexOf(currentBase)
  const stepIdx = AGENT_ORDER.indexOf(agent)
  if (stepIdx < currentIdx) return "done"
  if (stepIdx === currentIdx) return status === "failed" ? "failed" : "running"
  return "pending"
}

export default function AgentPipeline({ currentAgent, status, roundsTaken }) {
  const visibleAgents = AGENT_ORDER.filter(a => {
    if (a === "router") return roundsTaken && roundsTaken > 1
    return true
  })

  return (
    <div className="flex items-center w-full gap-0 select-none">
      {visibleAgents.map((agent, i, arr) => {
        const state = getStepState(agent, currentAgent, status)
        const IconComponent = AGENT_ICONS[agent]
        const isLast = i === arr.length - 1

        return (
          <div key={agent} className="flex items-center flex-1 min-w-0">
            <Tooltip>
              <TooltipTrigger asChild>
                <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full cursor-help transition-all duration-300 shrink-0 ${
                  state === "done"
                    ? "bg-green-050 border border-green-200 text-green-700"
                    : state === "running"
                    ? "bg-blue-600 border border-blue-500 text-white shadow-[0_0_12px_rgba(37,99,235,0.4)]"
                    : state === "failed"
                    ? "bg-red-100 border border-red-200 text-red-600"
                    : "bg-surface-base border border-slate-200 text-slate-400"
                }`}>
                  {state === "done" ? (
                    <Check className="w-3 h-3 stroke-[3px]" />
                  ) : state === "failed" ? (
                    <AlertCircle className="w-3 h-3" />
                  ) : (
                    <IconComponent className={`w-3 h-3 ${state === "running" ? "animate-pulse" : ""}`} />
                  )}
                  <span className="text-[10px] font-bold capitalize tracking-wide hidden sm:block">
                    {agent}
                  </span>
                </div>
              </TooltipTrigger>
              <TooltipContent
                side="bottom"
                className="bg-slate-900 text-white border-slate-800 text-xs p-3 shadow-card-lg rounded-lg max-w-[240px]"
              >
                <div className="font-semibold capitalize mb-1 flex items-center gap-1.5">
                  <span className={`w-1.5 h-1.5 rounded-full ${
                    state === "done" ? "bg-green-500" :
                    state === "running" ? "bg-blue-400 animate-pulse" : "bg-slate-500"
                  }`} />
                  {agent}
                </div>
                <p className="text-slate-400 leading-normal">{AGENT_DESCRIPTIONS[agent]}</p>
                {state === "running" && (
                  <p className="text-blue-400 text-[10px] font-medium border-t border-slate-800 pt-1 mt-1">
                    {AGENT_MESSAGES[agent]}
                  </p>
                )}
              </TooltipContent>
            </Tooltip>

            {/* Connector */}
            {!isLast && (
              <div className={`flex-1 h-px mx-1.5 transition-all duration-500 ${
                state === "done" ? "bg-green-300" : "bg-slate-200"
              }`} />
            )}
          </div>
        )
      })}
    </div>
  )
}
