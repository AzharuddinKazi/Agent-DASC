import { useState } from "react"
import ReportSections from "./ReportSections.jsx"
import ReportView from "./ReportView.jsx"
import PipelineHeader from "./PipelineHeader.jsx"
import PipelineTimeline from "./PipelineTimeline.jsx"
import ResearchProgress from "./ResearchProgress.jsx"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { AlertTriangle, MessageSquare, CircleStop, PauseCircle, ClipboardCheck } from "lucide-react"

export default function ReportPanel({ task, query, onFollowUp, isFollowUpBusy = false, onReviewDecision, isReviewSubmitting = false }) {
  const [steerText, setSteerText] = useState("")
  const isReport  = task?.task_type === "report"

  if (task?.status === "completed" && task?.final_result) {
    if (isReport) {
      return <ReportView task={task} query={query} onFollowUp={onFollowUp} isFollowUpBusy={isFollowUpBusy} />
    }
    return (
      <ReportSections
        result={task.final_result}
        script={task.current_script}
        plan={task.cumulative_plan}
        onFollowUp={onFollowUp}
        isFollowUpBusy={isFollowUpBusy}
      />
    )
  }

  if (task?.status === "stopped") {
    return (
      <Card className="border-border bg-muted/30 max-w-2xl mx-auto mt-6">
        <CardHeader>
          <CardTitle className="text-sm text-foreground flex items-center gap-2">
            <CircleStop className="w-4 h-4 text-muted-foreground" />
            Analysis Stopped
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            This analysis was stopped before it finished — no report was generated.
            {task.cumulative_plan?.length > 0 && " Any partial progress isn't recoverable; start a new analysis to try again."}
          </p>
        </CardContent>
      </Card>
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

  /* Loading / paused state */
  const handleSteerSubmit = (e) => {
    e.preventDefault()
    // Not yet wired to the backend — the pipeline has no mid-run steering endpoint.
    // Kept as a visible, honestly-disabled affordance until that lands.
  }

  // The task row has no live "current_round" column — cumulative_plan grows by one
  // entry per completed planner round, so its length is the best live proxy.
  const currentRound = task?.cumulative_plan?.length || 0
  const isPaused = task?.status === "paused"
  const isAwaitingReview = task?.status === "awaiting_review"

  // report_evaluator's verdict/gaps aren't persisted as their own tasks columns — they
  // only live in the LangGraph checkpoint and in this log entry (see
  // agents/report_evaluator.py and agents/graph.py's human_review_gate, which logs the
  // same shape on the checkpoint-pause path). Reading the latest one is the only way the
  // reviewer sees what the evaluator actually found, not just that a decision is pending.
  const latestEvaluation = (task?.logs || [])
    .filter(l => (l.agent === "report_evaluator" || l.agent === "human_review_gate") && l.verdict !== undefined)
    .at(-1)

  return (
    <div className="flex flex-col gap-4 w-full max-w-4xl mx-auto">
      {isPaused && (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="p-3.5 flex items-center gap-2.5">
            <PauseCircle className="w-4 h-4 text-amber-600 shrink-0" />
            <p className="text-sm text-amber-800">
              Paused — progress below is preserved. Resume (top right) restarts the step
              that was interrupted; everything before it stays as-is.
            </p>
          </CardContent>
        </Card>
      )}
      {isAwaitingReview && (
        <Card className="border-indigo-200 bg-indigo-50">
          <CardContent className="p-4 flex flex-col gap-3">
            <div className="flex items-start gap-2.5">
              <ClipboardCheck className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-indigo-900 font-medium">
                  Awaiting your review — refine further or finalize the report as-is.
                </p>
                {latestEvaluation && (
                  <p className="text-xs text-indigo-800/80 mt-1">
                    Evaluator recommends: <span className="font-semibold">{latestEvaluation.verdict}</span>
                    {latestEvaluation.gaps?.length > 0 && (
                      <> — gaps: {latestEvaluation.gaps.map(g => g.question).join("; ")}</>
                    )}
                  </p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2 pl-6.5">
              <Button
                size="sm" onClick={() => onReviewDecision?.("finalize")} disabled={isReviewSubmitting}
                className="h-8 text-body"
              >
                {isReviewSubmitting ? "Submitting…" : "Finalize now"}
              </Button>
              <Button
                size="sm" variant="outline" onClick={() => onReviewDecision?.("refine")} disabled={isReviewSubmitting}
                className="h-8 text-body border-indigo-200 text-indigo-700"
              >
                {isReviewSubmitting ? "Submitting…" : "Refine further"}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
      {isReport ? (
        <>
          <PipelineHeader query={query} currentRound={currentRound} isReport />
          <ResearchProgress task={task} />
        </>
      ) : (
        <>
          <PipelineHeader query={query} currentRound={currentRound} isReport={false} />
          <PipelineTimeline logs={task?.logs || []} currentScript={task?.current_script} />
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
