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

        return (
          <div key={agent} className="flex items-center flex-1 min-w-0">
            <Tooltip>
              <TooltipTrigger asChild>
                <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full cursor-help transition-all duration-200 border text-[10px] font-semibold capitalize tracking-wide ${
                  state === "done"
                    ? "bg-zinc-900 border-zinc-900 text-white"
                    : state === "running"
                    ? "bg-foreground border-foreground text-background shadow-sm"
                    : state === "failed"
                    ? "bg-danger/10 border-danger/30 text-danger"
                    : "bg-background border-border text-muted-foreground"
                }`}>
                  {state === "done" ? (
                    <Check className="w-3 h-3 stroke-[2.5px]" />
                  ) : state === "failed" ? (
                    <AlertCircle className="w-3 h-3" />
                  ) : (
                    <Icon className={`w-3 h-3 ${state === "running" ? "animate-pulse" : ""}`} />
                  )}
                  <span className="hidden sm:block">{agent}</span>
                </div>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-[200px]">
                <p className="font-semibold capitalize mb-0.5 text-xs">{agent}</p>
                <p className="text-muted-foreground text-xs leading-snug">{AGENT_DESCRIPTIONS[agent]}</p>
              </TooltipContent>
            </Tooltip>

            {!isLast && (
              <div className={`flex-1 h-px mx-1.5 transition-colors duration-500 ${
                state === "done" ? "bg-zinc-900" : "bg-border"
              }`} />
            )}
          </div>
        )
      })}
    </div>
  )
}
