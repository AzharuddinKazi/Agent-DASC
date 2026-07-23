import { Card, CardContent } from "@/components/ui/card"
import { Loader2 } from "lucide-react"

const AGENT_LABELS = {
  analyzer:               "Analyzer",
  question_generator:     "Question Generator",
  planner:                "Planner",
  coder:                  "Coder",
  executor:               "Executor",
  verifier:               "Verifier",
  debugger:                "Debugger",
  router:                 "Router",
  sub_result_collector:   "Sub-Result Collector",
  writer:                 "Writer",
  report_evaluator:       "Report Evaluator",
  gap_question_generator: "Gap Question Generator",
  report_finalizer:       "Report Finalizer",
  finalizer:              "Finalizer",
}

function agentLabel(entry) {
  const base = entry.agent?.startsWith("planner") ? "planner" : entry.agent
  const label = AGENT_LABELS[base] || entry.agent
  return entry.round ? `${label} · Round ${entry.round}` : label
}

function durationBetween(a, b) {
  if (!a || !b) return null
  const ms = new Date(b).getTime() - new Date(a).getTime()
  if (ms < 0 || !isFinite(ms)) return null
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`
}

// Collapse consecutive "running" + "success"/"error" log pairs for the same
// agent+round into a single timeline entry (mirrors one pipeline step).
function collapseSteps(logs) {
  const steps = []
  for (const entry of logs) {
    const last = steps[steps.length - 1]
    const sameStep = last && last.agent === entry.agent && last.round === entry.round && last.status !== "success" && last.status !== "error"
    if (sameStep) {
      last.finishedAt = entry.ts
      last.finalStatus = entry.status
      last.message = entry.message
    } else {
      steps.push({
        agent: entry.agent, round: entry.round, startedAt: entry.ts,
        finishedAt: entry.status === "running" ? null : entry.ts,
        finalStatus: entry.status, message: entry.message,
      })
    }
  }
  return steps
}

export default function PipelineTimeline({ logs = [], currentScript, isRunning }) {
  const steps = collapseSteps(logs)
  // Some agents (Planner, Coder) only ever log a single "running" event — there's no
  // matching success/error log to close them out. If a later step has already started,
  // this one is necessarily done; only the actual last step can still be "running".
  steps.forEach((step, i) => {
    if (step.finalStatus === "running" && i < steps.length - 1) {
      step.finalStatus = "success"
      step.finishedAt = steps[i + 1].startedAt
    }
  })

  return (
    <Card>
      <CardContent className="pt-5 pb-4">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-4">
          Agent Pipeline
        </p>
        <div className="flex flex-col">
          {steps.map((step, i) => {
            const running = step.finalStatus === "running"
            const failed  = step.finalStatus === "error"
            const dur = durationBetween(step.startedAt, step.finishedAt)
            const showCode = step.agent === "executor" && step.finalStatus === "success" && currentScript

            return (
              <div key={i} className="flex gap-3">
                <div className="flex flex-col items-center shrink-0">
                  <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5 ${
                    failed ? "bg-danger/10 text-danger border border-danger/30" :
                    running ? "bg-blue-50 text-blue-600 border border-blue-200" :
                    "bg-success/10 text-success border border-success/30"
                  }`}>
                    {running ? <Loader2 className="w-3 h-3 animate-spin" /> : failed ? "!" : "✓"}
                  </div>
                  {i < steps.length - 1 && <div className="w-px flex-1 bg-border my-1" style={{ minHeight: 16 }} />}
                </div>
                <div className={`flex-1 min-w-0 ${i < steps.length - 1 ? "pb-4" : ""}`}>
                  <div className="flex items-center justify-between gap-2">
                    <p className={`text-sm font-semibold ${running ? "text-blue-600" : "text-foreground"}`}>{agentLabel(step)}</p>
                    {dur && <span className="text-[11px] text-muted-foreground font-mono shrink-0">{dur}</span>}
                  </div>
                  <p className={`text-xs mt-0.5 leading-snug ${running ? "text-blue-600" : "text-muted-foreground"}`}>{step.message}</p>
                  {showCode && (
                    <pre className="mt-2 bg-muted/50 border border-border rounded-md p-2.5 text-[11px] font-mono text-muted-foreground overflow-x-auto max-h-24 overflow-y-auto">
                      {currentScript.split("\n").slice(0, 4).join("\n")}
                      {currentScript.split("\n").length > 4 ? "\n…" : ""}
                    </pre>
                  )}
                </div>
              </div>
            )
          })}
          {steps.length === 0 && (
            <p className="text-xs text-muted-foreground">Waiting for pipeline to start…</p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
