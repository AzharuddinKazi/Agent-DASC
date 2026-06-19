import { AGENT_MESSAGES } from "@/constants"

export default function StatusMessage({ currentAgent, status, rounds }) {
  if (status === "completed") return (
    <div className="flex items-center gap-2 text-xs text-green-400">
      <i className="ti ti-circle-check text-sm" />
      Analysis complete · {rounds} rounds
    </div>
  )
  if (status === "failed") return (
    <div className="flex items-center gap-2 text-xs text-red-400">
      <i className="ti ti-alert-circle text-sm" />
      Analysis failed
    </div>
  )
  if (!currentAgent) return (
    <div className="flex items-center gap-2 text-xs text-zinc-500">
      <div className="w-1.5 h-1.5 rounded-full bg-zinc-600 animate-pulse" />
      Starting up...
    </div>
  )

  const base = currentAgent.startsWith("planner") ? "planner" : currentAgent
  const roundNum = currentAgent.match(/round_(\d+)/)?.[1]

  return (
    <div className="flex items-center gap-2 text-xs text-zinc-400">
      <div className="w-1.5 h-1.5 rounded-full bg-violet-500 animate-pulse" />
      {AGENT_MESSAGES[base] ?? "Working..."}
      {roundNum && <span className="text-zinc-600">· round {roundNum}</span>}
    </div>
  )
}