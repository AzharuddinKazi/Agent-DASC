import { useEffect, useRef, useState } from "react"
import { ChevronDown, ChevronUp, Terminal } from "lucide-react"
import { Badge } from "@/components/ui/badge"

const STATUS_STYLES = {
  running: "text-info",
  success: "text-success",
  error:   "text-destructive",
  info:    "text-muted-foreground",
}

const STATUS_DOT = {
  running: "bg-info animate-pulse",
  success: "bg-success",
  error:   "bg-destructive",
  info:    "bg-muted-foreground/50",
}

const AGENT_LABELS = {
  analyzer:            "Analyzer",
  question_generator:  "Q-Gen",
  planner:             "Planner",
  coder:               "Coder",
  executor:            "Executor",
  verifier:            "Verifier",
  debugger:            "Debugger",
  router:              "Router",
  sub_result_collector:"Collector",
  writer:              "Writer",
  report_evaluator:    "Evaluator",
  gap_question_generator: "Gap-QGen",
  report_finalizer:    "Finalizer",
  finalizer:           "Finalizer",
}

function fmt(ts) {
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
  } catch { return "" }
}

export default function LogPanel({ logs = [], isRunning }) {
  const [open, setOpen] = useState(true)
  const bottomRef = useRef(null)

  useEffect(() => {
    if (open && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" })
    }
  }, [logs, open])

  return (
    <div className="border-b border-border bg-zinc-950 shrink-0">
      {/* Header toggle */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-2 hover:bg-white/5 transition-colors"
      >
        <span className="flex items-center gap-2 text-[11px] font-semibold text-zinc-400 uppercase tracking-widest">
          <Terminal className="w-3 h-3" />
          Pipeline Activity
          {logs.length > 0 && (
            <Badge variant="secondary" className="text-[9px] px-1.5 py-0 bg-zinc-800 text-zinc-400 border-0">
              {logs.length}
            </Badge>
          )}
          {isRunning && (
            <span className="w-1.5 h-1.5 rounded-full bg-info animate-pulse" />
          )}
        </span>
        {open
          ? <ChevronUp className="w-3.5 h-3.5 text-zinc-500" />
          : <ChevronDown className="w-3.5 h-3.5 text-zinc-500" />}
      </button>

      {open && (
        <div className="h-[220px] overflow-y-auto px-4 pb-3 font-mono text-[11px]">
          {logs.length === 0 ? (
            <p className="text-zinc-600 pt-2">Waiting for pipeline to start…</p>
          ) : (
            <div className="flex flex-col gap-0.5">
              {logs.map((entry, i) => (
                <div key={i} className="flex items-start gap-2 py-0.5 min-w-0">
                  {/* Time */}
                  <span className="text-zinc-600 shrink-0 tabular-nums w-[72px]">
                    {fmt(entry.ts)}
                  </span>

                  {/* Status dot */}
                  <span className={`mt-1.5 w-1.5 h-1.5 rounded-full shrink-0 ${STATUS_DOT[entry.status] || STATUS_DOT.info}`} />

                  {/* Agent badge */}
                  <span className="shrink-0 w-[72px] text-zinc-500 truncate">
                    {AGENT_LABELS[entry.agent] || entry.agent}
                  </span>

                  {/* Message */}
                  <span className={`leading-relaxed min-w-0 break-words ${STATUS_STYLES[entry.status] || "text-zinc-300"}`}>
                    {entry.message}
                  </span>
                </div>
              ))}
              <div ref={bottomRef} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
