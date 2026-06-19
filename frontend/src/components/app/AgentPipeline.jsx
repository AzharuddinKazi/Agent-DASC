import { AGENT_ORDER, AGENT_ICONS } from "@/constants"

function getStepState(agent, currentAgent) {
  if (!currentAgent) return "pending"
  const currentBase = currentAgent.startsWith("planner") ? "planner" : currentAgent
  const currentIdx  = AGENT_ORDER.indexOf(currentBase)
  const stepIdx     = AGENT_ORDER.indexOf(agent)
  if (stepIdx < currentIdx)  return "done"
  if (stepIdx === currentIdx) return "running"
  return "pending"
}

export default function AgentPipeline({ currentAgent, status }) {
  return (
    <div className="flex items-center gap-0">
      {AGENT_ORDER.filter(a => a !== "router").map((agent, i, arr) => {
        const state = status === "completed" ? "done"
          : status === "failed" ? (getStepState(agent, currentAgent) === "done" ? "done" : "pending")
          : getStepState(agent, currentAgent)

        return (
          <div key={agent} className="flex items-center flex-1">
            <div className="flex flex-col items-center gap-1.5 flex-1">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs border transition-all ${
                state === "done"    ? "bg-green-950/50 border-green-800/50 text-green-400" :
                state === "running" ? "bg-violet-950/50 border-violet-600/50 text-violet-400 shadow-[0_0_8px_rgba(124,58,237,0.4)]" :
                                      "bg-zinc-900 border-zinc-800 text-zinc-700"
              }`}>
                {state === "done"
                  ? <i className="ti ti-check text-xs" />
                  : <i className={`ti ${AGENT_ICONS[agent]} text-xs`} />
                }
              </div>
              <span className={`text-xs transition-colors ${
                state === "done"    ? "text-zinc-500" :
                state === "running" ? "text-violet-400" :
                                      "text-zinc-700"
              }`}>{agent}</span>
              <span className={`text-xs font-medium ${
                state === "done"    ? "text-green-500" :
                state === "running" ? "text-violet-400" :
                                      "text-zinc-700"
              }`}>
                {state === "done" ? "done" : state === "running" ? "running" : "·"}
              </span>
            </div>
            {i < arr.length - 1 && (
              <div className={`h-px flex-1 mb-6 mx-1 transition-colors ${
                state === "done" ? "bg-green-900/50" : "bg-zinc-800"
              }`} />
            )}
          </div>
        )
      })}
    </div>
  )
}