import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { Badge } from "@/components/ui/badge"
import { Check, Search, ListTodo, Code, Play, ShieldCheck, GitBranch, Sparkles, AlertCircle } from "lucide-react"

const AGENT_ORDER = ["analyzer", "planner", "coder", "executor", "verifier", "router", "finalizer"]

const AGENT_DESCRIPTIONS = {
  analyzer: "Profiles schema, row count, and column types",
  planner:  "Maps the query to a step-by-step analysis plan",
  coder:    "Writes Python to execute the plan",
  executor: "Runs the script in an isolated sandbox",
  verifier: "Checks result completeness and factual accuracy",
  router:   "Decides whether to refine or finalise",
  finalizer:"Structures the result into a clean report",
}

const AGENT_MESSAGES = {
  analyzer: "Profiling your data files...",
  planner:  "Planning the analysis approach...",
  coder:    "Writing analysis code...",
  executor: "Running the analysis...",
  verifier: "Checking result quality...",
  router:   "Refining the approach, starting next round...",
  finalizer:"Preparing your report...",
}

const AGENT_ICONS = {
  analyzer: Search, planner: ListTodo, coder: Code,
  executor: Play, verifier: ShieldCheck, router: GitBranch, finalizer: Sparkles,
}

function getStepState(agent, currentAgent, status) {
  if (status === "completed") return "done"
  if (!currentAgent) return "pending"
  const base = currentAgent.startsWith("planner") ? "planner" : currentAgent
  const cur  = AGENT_ORDER.indexOf(base)
  const idx  = AGENT_ORDER.indexOf(agent)
  if (idx < cur) return "done"
  if (idx === cur) return status === "failed" ? "failed" : "running"
  return "pending"
}

export default function AgentPipeline({ currentAgent, status, roundsTaken }) {
  const visible = AGENT_ORDER.filter(a => a !== "router" || (roundsTaken && roundsTaken > 1))

  return (
    <div className="flex items-center w-full gap-0 select-none">
      {visible.map((agent, i, arr) => {
        const state = getStepState(agent, currentAgent, status)
        const Icon  = AGENT_ICONS[agent]
        const isLast = i === arr.length - 1

        // Pick Badge variant based on state
        const badgeVariant =
          state === "done"    ? "outline" :
          state === "running" ? "default" :
          state === "failed"  ? "destructive" : "secondary"

        const badgeClass =
          state === "done"
            ? "border-green-200 bg-green-050 text-green-700 gap-1"
            : state === "running"
            ? "bg-primary text-primary-foreground gap-1 shadow-md shadow-primary/30"
            : state === "failed"
            ? "gap-1"
            : "gap-1 text-muted-foreground"

        return (
          <div key={agent} className="flex items-center flex-1 min-w-0">
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="cursor-help">
                  <Badge variant={badgeVariant} className={`${badgeClass} rounded-full px-2.5 py-1 h-auto text-[10px] font-bold capitalize tracking-wide`}>
                    {state === "done" ? (
                      <Check className="w-3 h-3 stroke-[3px]" />
                    ) : state === "failed" ? (
                      <AlertCircle className="w-3 h-3" />
                    ) : (
                      <Icon className={`w-3 h-3 ${state === "running" ? "animate-pulse" : ""}`} />
                    )}
                    <span className="hidden sm:inline">{agent}</span>
                  </Badge>
                </div>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-[220px]">
                <p className="font-semibold capitalize mb-0.5">{agent}</p>
                <p className="text-muted-foreground text-xs">{AGENT_DESCRIPTIONS[agent]}</p>
                {state === "running" && (
                  <p className="text-primary text-[10px] font-medium border-t border-border pt-1 mt-1">
                    {AGENT_MESSAGES[agent]}
                  </p>
                )}
              </TooltipContent>
            </Tooltip>

            {!isLast && (
              <div className={`flex-1 h-px mx-1 transition-colors duration-500 ${
                state === "done" ? "bg-green-300" : "bg-border"
              }`} />
            )}
          </div>
        )
      })}
    </div>
  )
}
