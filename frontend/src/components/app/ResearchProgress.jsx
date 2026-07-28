import { useMemo } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Check, Loader2 } from "lucide-react"

const PHASES = [
  { key: "question_generator", label: "Sub-question Generation" },
  { key: "analysis",           label: "DS-STAR Analysis" },
  { key: "writer",             label: "Report Writer" },
  { key: "refinement",         label: "Evaluator & Refinement" },
]

function currentPhase(agent) {
  if (!agent) return 0
  if (agent === "question_generator" || agent === "gap_question_generator") return agent === "gap_question_generator" ? 3 : 0
  if (agent === "writer") return 2
  if (["report_evaluator", "report_finalizer"].includes(agent)) return 3
  return 1 // analyzer, planner, coder, executor, verifier, debugger, router, sub_result_collector
}

// The task row has no live sub_questions/current_sub_idx columns — the backend only
// ever writes them into individual log entries' metadata (question_generator,
// gap_question_generator, sub_result_collector). Reconstruct progress from those.
function deriveFromLogs(logs) {
  const subQuestions = []
  let completedCount = 0
  let runningQuestion = null

  for (const entry of logs) {
    if (entry.agent === "question_generator" && entry.sub_questions) {
      subQuestions.push(...entry.sub_questions)
    }
    if (entry.agent === "gap_question_generator" && entry.new_questions) {
      subQuestions.push(...entry.new_questions)
    }
    if (entry.agent === "sub_result_collector" && entry.sub_q_idx) {
      completedCount = Math.max(completedCount, entry.sub_q_idx)
    }
    if (entry.sub_q_text && entry.status === "running") {
      runningQuestion = entry.sub_q_text
    }
  }
  return { subQuestions, completedCount, runningQuestion }
}

export default function ResearchProgress({ task }) {
  const logs = task?.logs || []
  const agent = task?.current_agent
  const phaseIdx = currentPhase(agent)

  const { subQuestions, completedCount, runningQuestion } = useMemo(() => deriveFromLogs(logs), [logs])
  const total = subQuestions.length || 1
  const overallPct = Math.round((completedCount / total) * (phaseIdx < 2 ? 90 : 100))

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardContent className="py-4">
          <p className="text-label font-semibold uppercase tracking-widest text-muted-foreground mb-3">Pipeline Phase</p>
          <div className="flex items-center">
            {PHASES.map((p, i) => (
              <div key={p.key} className="flex items-center flex-1 last:flex-none">
                <div className="flex flex-col items-center gap-1.5">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center border ${
                    i < phaseIdx ? "bg-success/10 border-success/30 text-success" :
                    i === phaseIdx ? "bg-purple-50 border-purple-300 text-purple-600" :
                    "bg-muted border-border text-muted-foreground"
                  }`}>
                    {i < phaseIdx ? <Check className="w-4 h-4" /> : i === phaseIdx ? <Loader2 className="w-4 h-4 animate-spin" /> : <span className="text-xs font-bold">{i + 1}</span>}
                  </div>
                  <span className={`text-label text-center max-w-[90px] leading-tight ${i === phaseIdx ? "text-purple-600 font-semibold" : "text-muted-foreground"}`}>{p.label}</span>
                </div>
                {i < PHASES.length - 1 && <div className={`flex-1 h-px mx-2 ${i < phaseIdx ? "bg-success/40" : "bg-border"}`} />}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="py-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-label font-semibold uppercase tracking-widest text-muted-foreground">Overall Progress</p>
            <span className="text-lg font-bold text-purple-600">{overallPct}%</span>
          </div>
          <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
            <div className="h-full bg-purple-500 rounded-full transition-all duration-700" style={{ width: `${overallPct}%` }} />
          </div>
          <p className="text-label text-muted-foreground mt-1.5">
            {completedCount} of {subQuestions.length} sub-question{subQuestions.length === 1 ? "" : "s"} complete
          </p>
        </CardContent>
      </Card>

      {subQuestions.length > 0 && (
        <Card>
          <CardContent className="py-4">
            <p className="text-label font-semibold uppercase tracking-widest text-muted-foreground mb-3">Sub-Questions</p>
            <div className="flex flex-col gap-2">
              {subQuestions.map((sq, i) => {
                const isDone    = i < completedCount
                const isCurrent = !isDone && sq === runningQuestion
                return (
                  <div key={i} className={`flex items-start gap-3 p-3 rounded-lg border ${isCurrent ? "border-purple-200 bg-purple-50/40" : "border-border"}`}>
                    <span className={`w-5 h-5 rounded flex items-center justify-center text-label font-bold shrink-0 mt-0.5 ${
                      isDone ? "bg-success/10 text-success" : isCurrent ? "bg-purple-100 text-purple-600" : "bg-muted text-muted-foreground"
                    }`}>{i + 1}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-foreground leading-snug">{sq}</p>
                      <p className="text-label mt-1">
                        {isDone && <span className="text-success font-medium">✓ Complete</span>}
                        {isCurrent && <span className="text-purple-600 font-medium">Running…</span>}
                        {!isDone && !isCurrent && <span className="text-muted-foreground">Queued</span>}
                      </p>
                    </div>
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
