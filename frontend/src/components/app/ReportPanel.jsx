import ReportSections from "./ReportSections.jsx"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
      <Card className="border-destructive/30 bg-destructive/5 max-w-2xl mx-auto mt-6">
        <CardHeader>
          <CardTitle className="text-sm text-destructive flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            Analysis Pipeline Failed
          </CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="text-xs text-destructive/80 leading-relaxed whitespace-pre-wrap bg-background p-4 rounded-md border border-destructive/20 font-mono overflow-x-auto">
            {task?.final_result ?? "An unexpected infrastructure error occurred."}
          </pre>
        </CardContent>
      </Card>
    )
  }

  /* Loading state */
  return (
    <div className="flex flex-col gap-6 w-full">
      {/* Status indicator */}
      <div className="flex flex-col items-center justify-center py-10 gap-5">
        <div className="relative flex items-center justify-center">
          <div className="absolute w-16 h-16 rounded-full bg-foreground/5 animate-ping opacity-50" style={{ animationDuration: '2s' }} />
          <div className="relative z-10 w-10 h-10 rounded-full bg-foreground flex items-center justify-center">
            <Zap className="w-5 h-5 text-background" strokeWidth={2.5} />
          </div>
        </div>
        <div className="text-center">
          {baseAgent && (
            <Badge variant="secondary" className="font-mono text-[10px] uppercase tracking-wider mb-2">
              {baseAgent}
            </Badge>
          )}
          <p className="text-sm font-semibold text-foreground">{getAgentDescription(rawAgent)}</p>
          <p className="text-xs text-muted-foreground mt-1">Typically completes in 30–90 seconds</p>
        </div>
      </div>

      {/* Skeleton — summary first, then table */}
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2">
          <Card>
            <CardContent className="p-5">
              <Skeleton className="h-3 w-32 mb-4" />
              <Skeleton className="h-3 w-full mb-2" />
              <Skeleton className="h-3 w-5/6 mb-2" />
              <Skeleton className="h-3 w-4/6" />
            </CardContent>
          </Card>
        </div>
        <Card>
          <CardContent className="p-5">
            <Skeleton className="h-3 w-24 mb-4" />
            <Skeleton className="h-3 w-full mb-3" />
            <Skeleton className="h-3 w-full mb-3" />
            <Skeleton className="h-3 w-full" />
          </CardContent>
        </Card>
      </div>
      <Skeleton className="h-72 w-full rounded-lg" />
    </div>
  )
}
