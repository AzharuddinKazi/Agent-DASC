import ReportSections from "./ReportSections.jsx"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { AlertTriangle, Zap } from "lucide-react"

function getAgentDescription(agent) {
  if (!agent) return "Initializing autonomous pipeline..."
  if (agent.startsWith("planner")) {
    const m = agent.match(/\d+/)
    return m ? `Formulating plan for iteration ${m[0]}...` : "Formulating analytical plan..."
  }
  return {
    analyzer: "Analyzing dataset schemas and preparing context...",
    coder:    "Translating plan into secure Pandas execution script...",
    executor: "Spinning up isolated Docker sandbox and executing code...",
    verifier: "Evaluating execution results against your original query...",
    router:   "Determining if further analysis is required...",
    debugger: "Execution failed. Analyzing traceback and writing code patch...",
    finalizer:"Formatting final report and data tables..."
  }[agent] || `Agent active: ${agent}`
}

export default function ReportPanel({ task, query, onFollowUp }) {
  const rawAgent  = task?.current_agent
  const baseAgent = rawAgent?.startsWith("planner") ? "planner" : rawAgent

  if (task?.status === "completed" && task?.final_result) {
    return (
      <ReportSections
        result={task.final_result}
        query={query}
        script={task.current_script}
        plan={task.cumulative_plan}
        taskId={task.task_id}
        onFollowUp={onFollowUp}
      />
    )
  }

  if (task?.status === "failed") {
    return (
      <Card className="border-red-200 bg-red-100 max-w-2xl mx-auto mt-8">
        <CardContent className="p-6">
          <div className="flex items-center gap-2 text-red-700 font-bold mb-3">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            Analysis Pipeline Failed
          </div>
          <pre className="text-xs text-red-800 leading-relaxed whitespace-pre-wrap bg-white/60 p-4 rounded-lg border border-red-200/60 font-mono overflow-x-auto">
            {task?.final_result ?? "An unexpected infrastructure error occurred."}
          </pre>
        </CardContent>
      </Card>
    )
  }

  /* Loading state */
  return (
    <div className="flex flex-col items-center justify-center min-h-[420px] gap-8 w-full">

      {/* Animated orb */}
      <div className="relative flex items-center justify-center">
        <div className="absolute w-20 h-20 rounded-full bg-primary/10 animate-ping opacity-40" style={{ animationDuration: '2s' }} />
        <div className="absolute w-14 h-14 rounded-full bg-primary/15 animate-ping opacity-60" style={{ animationDuration: '1.5s', animationDelay: '0.2s' }} />
        <div className="relative z-10 w-12 h-12 rounded-full bg-primary flex items-center justify-center shadow-lg shadow-primary/30">
          <Zap className="w-5 h-5 text-primary-foreground" strokeWidth={2.5} />
        </div>
      </div>

      <div className="flex flex-col items-center text-center gap-3">
        {baseAgent && (
          <Badge variant="secondary" className="font-mono text-[10px] uppercase tracking-wider">
            {baseAgent}
          </Badge>
        )}
        <p className="text-[15px] font-semibold text-foreground max-w-sm leading-snug">
          {getAgentDescription(rawAgent)}
        </p>
        <p className="text-sm text-muted-foreground max-w-xs leading-relaxed">
          The autonomous pipeline is working through your query. This typically takes 30–90 seconds.
        </p>
      </div>

      {/* Skeleton placeholders */}
      <div className="w-full max-w-xl flex flex-col gap-3">
        <Skeleton className="h-24 w-full rounded-lg" />
        <div className="grid grid-cols-3 gap-3">
          <Skeleton className="h-16 rounded-lg" />
          <Skeleton className="h-16 rounded-lg" />
          <Skeleton className="h-16 rounded-lg" />
        </div>
        <Skeleton className="h-40 w-full rounded-lg" />
      </div>
    </div>
  )
}
