import { Tooltip, TooltipContent, TooltipTrigger } from "../ui/tooltip"
import { Check, Search, ListTodo, Code, Play, ShieldCheck, GitBranch, Sparkles } from "lucide-react"

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
  if (stepIdx === currentIdx) {
    return status === "failed" ? "pending" : "running"
  }
  return "pending"
}

export default function AgentPipeline({ currentAgent, status, roundsTaken }) {
  // Only show router when rounds_taken > 1
  const visibleAgents = AGENT_ORDER.filter(a => {
    if (a === "router") {
      return (roundsTaken && roundsTaken > 1)
    }
    return true
  })

  return (
    <div className="flex items-center w-full justify-between relative select-none">
      {visibleAgents.map((agent, i, arr) => {
        const state = getStepState(agent, currentAgent, status)
        const IconComponent = AGENT_ICONS[agent]

        return (
          <div key={agent} className="flex-1 relative flex flex-col items-center">
            {/* Connector Line behind dots */}
            {i < arr.length - 1 && (
              <div 
                className={`absolute top-3 left-[50%] w-full h-[2px] -z-10 transition-colors duration-500 ${
                  state === "done" ? "bg-green-600/25" : "bg-slate-100"
                }`}
              />
            )}

            <Tooltip>
              <TooltipTrigger asChild>
                <div className="flex flex-col items-center cursor-help group">
                  {/* Dot */}
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center border text-[10px] transition-all duration-300 ${
                    state === "done"    ? "bg-green-100 border-[#86efac] text-green-600" :
                    state === "running" ? "bg-blue-100 border-[#93c5fd] text-blue-600 shadow-[0_0_0_3px_rgba(37,99,235,0.15)] animate-pulse" :
                                          "bg-slate-050 border-slate-200 text-slate-400 group-hover:bg-slate-100"
                  }`}>
                    {state === "done" ? (
                      <Check className="w-3.5 h-3.5 stroke-[3px]" />
                    ) : (
                      <IconComponent className="w-3 h-3" />
                    )}
                  </div>
                  
                  {/* Label underneath */}
                  <span className={`text-[10px] capitalize font-medium mt-1.5 transition-colors duration-300 ${
                    state === "done"    ? "text-green-600 font-semibold" :
                    state === "running" ? "text-blue-600 font-bold" :
                                          "text-slate-400"
                  }`}>
                    {agent}
                  </span>
                </div>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="bg-slate-900 text-white border-slate-800 text-xs p-3 shadow-lg rounded-md max-w-[240px]">
                <div className="font-semibold capitalize mb-1 flex items-center gap-1.5">
                  <span className={`w-1.5 h-1.5 rounded-full ${
                    state === "done" ? "bg-green-600" :
                    state === "running" ? "bg-blue-600 animate-pulse" : "bg-slate-400"
                  }`} />
                  {agent}
                </div>
                <p className="text-slate-400 leading-normal mb-1">{AGENT_DESCRIPTIONS[agent]}</p>
                {state === "running" && (
                  <p className="text-blue-400 text-[10px] font-medium border-t border-slate-800 pt-1 mt-1">
                    {AGENT_MESSAGES[agent]}
                  </p>
                )}
              </TooltipContent>
            </Tooltip>
          </div>
        )
      })}
    </div>
  )
}