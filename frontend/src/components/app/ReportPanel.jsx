import { useState } from "react"
import ReportSections from "./ReportSections.jsx"
import ReportView from "./ReportView.jsx"
import PipelineHeader from "./PipelineHeader.jsx"
import PipelineTimeline from "./PipelineTimeline.jsx"
import ResearchProgress from "./ResearchProgress.jsx"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { AlertTriangle, MessageSquare } from "lucide-react"

export default function ReportPanel({ task, query, onFollowUp }) {
  const [steerText, setSteerText] = useState("")
  const isReport  = task?.task_type === "report"

  if (task?.status === "completed" && task?.final_result) {
    if (isReport) {
      return <ReportView task={task} query={query} onFollowUp={onFollowUp} />
    }
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
  const handleSteerSubmit = (e) => {
    e.preventDefault()
    // Not yet wired to the backend — the pipeline has no mid-run steering endpoint.
    // Kept as a visible, honestly-disabled affordance until that lands.
  }

  // The task row has no live "current_round" column — cumulative_plan grows by one
  // entry per completed planner round, so its length is the best live proxy.
  const currentRound = task?.cumulative_plan?.length || 0

  return (
    <div className="flex flex-col gap-4 w-full max-w-4xl mx-auto">
      {isReport ? (
        <>
          <PipelineHeader query={query} currentRound={currentRound} isReport />
          <ResearchProgress task={task} />
        </>
      ) : (
        <>
          <PipelineHeader query={query} currentRound={currentRound} isReport={false} />
          <PipelineTimeline logs={task?.logs || []} currentScript={task?.current_script} isRunning />
        </>
      )}

      <form onSubmit={handleSteerSubmit}>
        <Card className="border-dashed">
          <CardContent className="p-2.5 flex items-center gap-2">
            <MessageSquare className="w-3.5 h-3.5 text-muted-foreground shrink-0 ml-1.5" />
            <Input
              value={steerText}
              onChange={e => setSteerText(e.target.value)}
              placeholder="Steer the analysis (optional) — not yet available mid-run"
              disabled
              className="border-none bg-transparent shadow-none focus-visible:ring-0 h-8 text-sm"
            />
            <Button type="submit" disabled size="sm" variant="outline" className="shrink-0">Send</Button>
          </CardContent>
        </Card>
      </form>
    </div>
  )
}
