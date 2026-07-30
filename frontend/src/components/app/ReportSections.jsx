import { useState, useMemo } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  ChevronRight, ChevronDown, ChevronUp, ChevronsUpDown,
  Download, ListTodo, CheckCircle2, RotateCcw, FileStack,
  TrendingUp, Send, Sparkles, ShieldAlert,
  ThumbsUp, ThumbsDown, Flag
} from "lucide-react"
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism"
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from "recharts"

// ── Colour palette for charts — the brand ramp (--color-chart-1..5) plus two
// borrowed hues for the rare chart with more than 5 series ─────────────────────
const CHART_COLORS = [
  "var(--color-chart-1)", "var(--color-chart-2)", "var(--color-chart-3)",
  "var(--color-chart-4)", "var(--color-chart-5)", "var(--color-info)", "#7c3aed",
]

// ── Chart renderer ────────────────────────────────────────────────────────────
// Bare — no Card of its own. Lives inside the merged Evidence card (chart + the table
// it's drawn from, together) rather than as a disconnected section a reader has to
// mentally reconnect to the table below it.
function DataChart({ chart }) {
  if (!chart || !chart.data || chart.data.length === 0) return null

  const tickStyle  = { fontSize: 11, fill: "var(--color-muted-foreground)", fontFamily: "var(--font-sans)" }
  const tooltipStyle = { fontSize: 12, fontFamily: "var(--font-sans)", border: "1px solid var(--color-border)", borderRadius: 6, boxShadow: "0 2px 8px rgba(0,0,0,.06)" }

  const sharedProps = { data: chart.data, margin: { top: 4, right: 16, left: 0, bottom: 4 } }

  return (
    <ResponsiveContainer width="100%" height={260}>
      {chart.type === "pie" ? (
        <PieChart>
          <Pie data={chart.data} dataKey={chart.y_key} nameKey={chart.x_key} cx="50%" cy="50%" outerRadius={100} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false}>
            {chart.data.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
        </PieChart>
      ) : chart.type === "line" ? (
        <LineChart {...sharedProps}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis dataKey={chart.x_key} tick={tickStyle} label={{ value: chart.x_label, position: "insideBottom", offset: -2, style: tickStyle }} />
          <YAxis tick={tickStyle} label={{ value: chart.y_label, angle: -90, position: "insideLeft", style: tickStyle }} />
          <Tooltip contentStyle={tooltipStyle} />
          <Line type="monotone" dataKey={chart.y_key} stroke="var(--color-chart-2)" strokeWidth={2} dot={{ r: 3, fill: "var(--color-chart-2)" }} activeDot={{ r: 5 }} />
        </LineChart>
      ) : (
        <BarChart {...sharedProps} layout="vertical">
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
          <XAxis type="number" tick={tickStyle} label={{ value: chart.y_label, position: "insideBottom", offset: -2, style: tickStyle }} />
          <YAxis dataKey={chart.x_key} type="category" tick={tickStyle} width={140} />
          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "var(--color-muted)" }} />
          <Bar dataKey={chart.y_key} radius={[0, 4, 4, 0]}>
            {chart.data.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
          </Bar>
        </BarChart>
      )}
    </ResponsiveContainer>
  )
}

// ── Key findings strip ────────────────────────────────────────────────────────
// Demoted from a dark card competing with the headline for attention (it used to sit
// ABOVE the actual answer) to a lighter, secondary card directly beneath it — still
// distinct, but reading as "supporting detail" rather than a second headline.
function KeyFindings({ findings }) {
  if (!findings || findings.length === 0) return null
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-muted-foreground" />
          Key Findings
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <ul className="flex flex-col gap-2">
          {findings.map((f, i) => (
            <li key={i} className="flex items-start gap-2.5 text-sm text-muted-foreground leading-snug">
              <span className="w-5 h-5 rounded-full bg-muted flex items-center justify-center text-label font-bold shrink-0 mt-0.5 text-foreground">{i + 1}</span>
              {f}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}

// ── Feedback bar ──────────────────────────────────────────────────────────────
// Not yet persisted to a backend feedback store — the API has no endpoint for it.
// Kept local-only (per-session) until that lands; the PRD calls for weekly review
// of "Flag as incorrect" submissions, which needs real storage first.
function FeedbackBar() {
  const [vote, setVote] = useState(null)
  return (
    <div className="flex items-center justify-between px-1">
      <p className="text-xs text-muted-foreground">Was this analysis helpful?</p>
      <div className="flex items-center gap-2">
        <Button
          variant={vote === "up" ? "default" : "outline"} size="sm"
          onClick={() => setVote(v => v === "up" ? null : "up")}
          className="h-7 text-xs gap-1.5"
        >
          <ThumbsUp className="w-3 h-3" /> Helpful
        </Button>
        <Button
          variant={vote === "down" ? "default" : "outline"} size="sm"
          onClick={() => setVote(v => v === "down" ? null : "down")}
          className="h-7 text-xs gap-1.5"
        >
          <ThumbsDown className="w-3 h-3" /> Not helpful
        </Button>
        <Button variant="outline" size="sm" className="h-7 text-xs gap-1.5 text-destructive hover:text-destructive">
          <Flag className="w-3 h-3" /> Flag issue
        </Button>
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function ReportSections({ result, script, plan = [], onFollowUp, isFollowUpBusy = false }) {
  const [showCode, setShowCode]         = useState(false)
  const [showAudit, setShowAudit]       = useState(false)
  const [showPlan, setShowPlan]         = useState(false)
  const [followUpText, setFollowUpText] = useState("")
  const [sortCol, setSortCol]           = useState(null)
  const [sortDir, setSortDir]           = useState("desc")

  // ── Parse result ────────────────────────────────────────────────────────────
  const parsed = useMemo(() => {
    if (!result) return null
    try {
      let s = typeof result === "string" ? result.trim() : JSON.stringify(result)
      if (s.startsWith("```json")) s = s.replace(/^```json/, "").replace(/```$/, "")
      else if (s.startsWith("```"))  s = s.replace(/^```/, "").replace(/```$/, "")
      return JSON.parse(s.trim())
    } catch { return null }
  }, [result])

  // If the Finalizer's output didn't parse as JSON, don't dump the raw string into
  // the "Analysis Summary" card as if it were prose — that's confusing (looked like a
  // rendering bug rather than what it actually was: unparseable output). Say so plainly
  // and put the raw text in the monospace fallback block below instead.
  const parseFailed  = !parsed && !!result
  const summary      = parsed?.summary || (parseFailed ? "Could not parse structured output — see raw result below." : "Analysis complete.")
  const keyFindings  = parsed?.key_findings || []
  const columns      = parsed?.columns      || []
  const rows         = parsed?.rows         || []
  const chart        = parsed?.chart        || null
  const rawText      = parsed?.raw || (parseFailed ? (typeof result === "string" ? result : JSON.stringify(result, null, 2)) : "")
  const hasTableData = columns.length > 0 && rows.length > 0

  // Real provenance, injected server-side by finalizer.py — not a guess. Replaces a
  // previous client-side estimate (`plan.length * 2500` tokens) that had no connection
  // to what actually happened during the run.
  const debugAttempts = parsed?.debug_attempts ?? null
  const filesUsed      = parsed?.files_used || []
  const rounds          = plan.length || 1

  // ── Numeric detection ───────────────────────────────────────────────────────
  const numericColumnMap = useMemo(() => {
    const map = {}
    if (!hasTableData) return map
    for (let c = 0; c < columns.length; c++) {
      let ok = true, checks = 0
      for (let r = 0; r < Math.min(rows.length, 10); r++) {
        const v = rows[r][c]
        if (v == null || v === "") continue
        checks++
        if (isNaN(parseFloat(String(v).replace(/[^0-9.-]/g, "")))) { ok = false; break }
      }
      map[c] = ok && checks > 0
    }
    return map
  }, [columns, rows, hasTableData])

  const columnMaxValues = useMemo(() => {
    const m = {}
    if (!hasTableData) return m
    for (let c = 0; c < columns.length; c++) {
      if (!numericColumnMap[c]) continue
      m[c] = Math.max(...rows.map(r => parseFloat(String(r[c]).replace(/[^0-9.-]/g, "")) || 0))
    }
    return m
  }, [columns, rows, hasTableData, numericColumnMap])

  // ── Top row, for a quiet in-table highlight ─────────────────────────────────
  // Replaces the old "Risk Highlights" card, which guessed a business meaning (Highest
  // Risk / Watch / Lowest Exposure) from column-name keywords and got prominent
  // placement for every query regardless of whether that framing made any sense for it.
  // This keeps the one genuinely useful part — surfacing the row with the largest value
  // in whatever the most metric-like numeric column is — as a subtle table affordance
  // instead of a competing, mislabeled headline.
  const topRow = useMemo(() => {
    if (!hasTableData) return null
    let metricIdx = -1
    for (let i = 0; i < columns.length; i++) {
      const c = columns[i].toLowerCase()
      if (["score","risk","ratio","amount","volume","count","sum","total","value","rate"].some(k => c.includes(k))) { metricIdx = i; break }
    }
    if (metricIdx === -1) for (let i = 0; i < columns.length; i++) { if (numericColumnMap[i]) { metricIdx = i; break } }
    if (metricIdx === -1) return null
    return [...rows].sort((a, b) =>
      (parseFloat(String(b[metricIdx]).replace(/[^0-9.-]/g,""))||0) - (parseFloat(String(a[metricIdx]).replace(/[^0-9.-]/g,""))||0)
    )[0]
  }, [hasTableData, columns, rows, numericColumnMap])

  // ── Sorting ─────────────────────────────────────────────────────────────────
  const handleSort = c => { if (sortCol === c) setSortDir(d => d === "asc" ? "desc" : "asc"); else { setSortCol(c); setSortDir("desc") } }

  const sortedRows = useMemo(() => {
    if (!hasTableData) return []
    let list = [...rows]
    if (sortCol !== null) {
      list.sort((a, b) => {
        const na = parseFloat(String(a[sortCol]).replace(/[^0-9.-]/g,"")), nb = parseFloat(String(b[sortCol]).replace(/[^0-9.-]/g,""))
        if (!isNaN(na) && !isNaN(nb)) return sortDir === "asc" ? na - nb : nb - na
        return sortDir === "asc" ? String(a[sortCol]).localeCompare(String(b[sortCol])) : String(b[sortCol]).localeCompare(String(a[sortCol]))
      })
    }
    return list
  }, [rows, sortCol, sortDir, hasTableData])

  const riskColIdx = useMemo(() => columns.findIndex(c => ["risk","level","alert","class"].some(k => c.toLowerCase().includes(k))), [columns])

  const renderBadge = val => {
    const n = String(val).toLowerCase()
    if (["high","danger","critical"].some(k => n.includes(k)))
      return <Badge variant="outline" className="text-label font-bold uppercase tracking-wider bg-danger/10 text-danger border-danger/30">High</Badge>
    if (["medium","med","warning","watch"].some(k => n.includes(k)))
      return <Badge variant="outline" className="text-label font-bold uppercase tracking-wider bg-warning-bg text-warning border-warning/30">Medium</Badge>
    if (["low","safe","info"].some(k => n.includes(k)))
      return <Badge variant="outline" className="text-label font-bold uppercase tracking-wider bg-success-bg text-success border-success/30">Low</Badge>
    return val
  }

  const exportCSV = () => {
    if (!hasTableData) return
    const lines = [columns.map(c => `"${String(c).replace(/"/g,'""')}"`).join(','), ...rows.map(r => r.map(c => `"${String(c).replace(/"/g,'""')}"`).join(','))]
    const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(new Blob([lines.join('\n')], {type:'text/csv'})), download: `ds_star_${Date.now()}.csv`, style: 'visibility:hidden' })
    document.body.appendChild(a); a.click(); document.body.removeChild(a)
  }

  const handleSubmit = e => { e.preventDefault(); if (!followUpText.trim()) return; onFollowUp(followUpText); setFollowUpText("") }

  return (
    <div className="flex flex-col gap-5 pb-24 w-full">

      {/* ── Headline: the actual answer, given the visual weight it deserves — was
          previously a plain muted paragraph third in reading order, below a stat-tile
          grid and a dark Key Findings card. This is that answer, promoted to be the
          first thing read, with real (not fabricated) trust signal attached inline. ── */}
      <Card className="border-foreground/10 bg-foreground text-background">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold text-background/90 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4" />
            Analysis Summary
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-base font-medium leading-relaxed">{summary}</p>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-4 pt-3 border-t border-background/10 text-label text-background/60">
            {hasTableData && <span>{rows.length.toLocaleString()} row{rows.length === 1 ? "" : "s"} analysed</span>}
            {filesUsed.length > 0 && (
              <>
                {hasTableData && <span>·</span>}
                <span className="flex items-center gap-1"><FileStack className="w-3 h-3" />{filesUsed.length} file{filesUsed.length === 1 ? "" : "s"}</span>
              </>
            )}
            {debugAttempts !== null && (
              <>
                <span>·</span>
                {debugAttempts === 0 ? (
                  <span>ran clean, no retries</span>
                ) : (
                  <span className="flex items-center gap-1 text-warning"><RotateCcw className="w-3 h-3" />resolved after {debugAttempts} retry{debugAttempts === 1 ? "" : "ies"}</span>
                )}
              </>
            )}
          </div>
        </CardContent>
      </Card>

      <KeyFindings findings={keyFindings} />

      {/* ── Evidence: chart and its backing table together in one card, not two
          disconnected sections a reader has to mentally reconnect. ── */}
      {(chart || hasTableData || (!hasTableData && rawText)) && (
        <Card>
          <CardHeader className="pb-0">
            <div className="flex items-center justify-between gap-3">
              <div>
                <CardTitle className="text-sm font-semibold">{chart?.title || "Evidence"}</CardTitle>
                {hasTableData && (
                  <p className="text-xs text-muted-foreground mt-0.5">{rows.length} records · {columns.length} columns</p>
                )}
              </div>
              {hasTableData && (
                <Button variant="outline" size="sm" onClick={exportCSV} className="gap-1.5 h-7 text-xs shrink-0">
                  <Download className="w-3.5 h-3.5" />
                  Export CSV
                </Button>
              )}
            </div>
          </CardHeader>

          <CardContent className={chart ? "pt-3" : "p-0 mt-3"}>
            {chart && <DataChart chart={chart} />}

            {hasTableData && (
              <div className={`overflow-x-auto ${chart ? "mt-4 -mx-6" : ""}`}>
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/40 hover:bg-muted/40 border-y border-border">
                      <TableHead className="w-10 px-4 py-2.5 text-label font-bold uppercase tracking-widest text-muted-foreground">#</TableHead>
                      {columns.map((col, idx) => {
                        const isSorted = sortCol === idx
                        const isNum    = numericColumnMap[idx]
                        return (
                          <TableHead
                            key={idx}
                            onClick={() => handleSort(idx)}
                            className={`px-4 py-2.5 text-label font-bold uppercase tracking-widest text-muted-foreground cursor-pointer hover:text-foreground select-none transition-colors ${isNum ? "text-right" : "text-left"} ${isSorted ? "text-foreground" : ""}`}
                          >
                            <span className={`flex items-center gap-1 ${isNum ? "justify-end" : ""}`}>
                              {col}
                              {isSorted ? sortDir === "asc" ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />
                                : <ChevronsUpDown className="w-3 h-3 opacity-30" />}
                            </span>
                          </TableHead>
                        )
                      })}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sortedRows.map((row, i) => (
                      <TableRow key={i} className={`border-b border-border/50 hover:bg-muted/30 transition-colors ${row === topRow ? "bg-accent/40" : ""}`}>
                        <TableCell className="px-4 py-3 w-10 tabular-nums text-label text-muted-foreground font-medium">{i + 1}</TableCell>
                        {row.map((cell, ci) => {
                          if (ci === riskColIdx) return <TableCell key={ci} className="px-4 py-3">{renderBadge(cell)}</TableCell>
                          if (ci === 0) return <TableCell key={ci} className="px-4 py-3 text-sm font-semibold text-foreground">{cell}</TableCell>
                          if (numericColumnMap[ci]) {
                            const val = parseFloat(String(cell).replace(/[^0-9.-]/g,"")) || 0
                            const pct = Math.round(val / (columnMaxValues[ci] || 1) * 100)
                            return (
                              <TableCell key={ci} className="px-4 py-3 text-right">
                                <p className="text-sm font-semibold text-foreground tabular-nums">{typeof cell === "number" ? cell.toLocaleString() : cell}</p>
                                <div className="w-16 h-1 bg-muted rounded-full overflow-hidden ml-auto mt-1">
                                  <div className="h-full bg-foreground/30 rounded-full" style={{ width: `${pct}%` }} />
                                </div>
                              </TableCell>
                            )
                          }
                          return <TableCell key={ci} className="px-4 py-3 text-sm text-muted-foreground">{cell}</TableCell>
                        })}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}

            {!hasTableData && rawText && (
              <p className="font-mono text-xs text-muted-foreground leading-relaxed overflow-x-auto whitespace-pre-wrap p-5">{rawText}</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* ── Collapsible: Analysis Plan ── */}
      {plan && plan.length > 0 && (
        <Card>
          <button
            onClick={() => setShowPlan(v => !v)}
            className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-muted/30 transition-colors cursor-pointer rounded-lg"
          >
            <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
              {showPlan ? <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" /> : <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />}
              <ListTodo className="w-4 h-4 text-muted-foreground" />
              Analysis Plan
            </span>
            <Badge variant="secondary" className="text-label">{plan.length} steps</Badge>
          </button>
          {showPlan && (
            <>
              <Separator />
              <CardContent className="pt-3 pb-4">
                <div className="flex flex-col gap-0">
                  {plan.map((step, idx) => (
                    <div key={idx} className="flex items-start gap-3 py-2.5 border-b border-border last:border-none">
                      <div className="w-5 h-5 rounded-full bg-success/10 border border-success/30 flex items-center justify-center shrink-0 mt-0.5">
                        <CheckCircle2 className="w-3.5 h-3.5 text-success" />
                      </div>
                      <p className="text-sm text-muted-foreground leading-snug flex-1">
                        <span className="font-semibold text-foreground mr-1.5">Step {idx + 1}.</span>{step}
                      </p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </>
          )}
        </Card>
      )}

      {/* ── Collapsible: Audit Details + Python Script ── */}
      <Card className="border-dashed">
        <button
          onClick={() => setShowAudit(v => !v)}
          className="w-full flex items-center justify-between px-5 py-3 hover:bg-muted/30 transition-colors cursor-pointer rounded-lg"
        >
          <span className="flex items-center gap-2 text-sm text-muted-foreground font-medium">
            {showAudit ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            Audit Details
          </span>
          <span className="text-label text-muted-foreground tabular-nums">
            {rounds} round{rounds === 1 ? "" : "s"}{debugAttempts ? ` · ${debugAttempts} retr${debugAttempts === 1 ? "y" : "ies"}` : ""}
          </span>
        </button>

        {showAudit && (
          <>
            <Separator />
            <div className="grid grid-cols-2 md:grid-cols-4 gap-0 divide-x divide-border border-b border-border">
              {[
                { label: "Analysis Rounds", value: rounds.toString(), unit: rounds === 1 ? "iteration" : "iterations", icon: ListTodo },
                { label: "Debug Retries",   value: debugAttempts !== null ? debugAttempts.toString() : "—", unit: debugAttempts ? "to reach a working script" : "ran clean", icon: RotateCcw },
                { label: "Files Used",      value: filesUsed.length.toString(), unit: filesUsed.length === 1 ? "dataset" : "datasets", icon: FileStack },
                { label: "Data Rows",       value: hasTableData ? rows.length.toString() : "—", unit: hasTableData ? `${columns.length} columns` : "no table data", icon: TrendingUp },
              ].map(({ label, value, unit, icon: Icon }) => (
                <div key={label} className="flex items-start gap-3 px-5 py-4">
                  <div className="w-7 h-7 rounded-md border border-border flex items-center justify-center text-muted-foreground shrink-0">
                    <Icon className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <p className="text-label text-muted-foreground font-medium">{label}</p>
                    <p className="text-base font-bold text-foreground leading-tight">{value}</p>
                    <p className="text-label text-muted-foreground">{unit}</p>
                  </div>
                </div>
              ))}
            </div>

            {filesUsed.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap px-5 py-3 border-b border-border">
                <span className="text-label text-muted-foreground font-medium uppercase tracking-wider">Datasets:</span>
                {filesUsed.map(f => (
                  <Badge key={f} variant="secondary" className="text-label font-mono">{f}</Badge>
                ))}
              </div>
            )}

            <button
              onClick={() => setShowCode(v => !v)}
              className="w-full flex items-center justify-between px-5 py-3 hover:bg-muted/30 transition-colors cursor-pointer"
            >
              <span className="flex items-center gap-2 text-sm text-muted-foreground font-medium">
                {showCode ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                Python Script
              </span>
              <Badge variant="secondary" className="font-mono text-label">.py</Badge>
            </button>
            {showCode && (
              <>
                <Separator />
                <SyntaxHighlighter
                  language="python"
                  style={oneLight}
                  customStyle={{ background: 'var(--color-neutral-050)', padding: '16px', margin: 0, fontSize: '12px', lineHeight: '1.6', fontFamily: "'Source Code Pro', monospace", borderRadius: '0 0 0.5rem 0.5rem' }}
                >
                  {script || "# No code executed."}
                </SyntaxHighlighter>
              </>
            )}
          </>
        )}
      </Card>

      <FeedbackBar />

      {/* ── Follow-up bar ── */}
      <div className="sticky bottom-0 -mx-6 px-6 pb-4 pt-4 bg-gradient-to-t from-background via-background/95 to-transparent z-30">
        <form onSubmit={handleSubmit}>
          <Card className="shadow-md border-border focus-within:ring-2 focus-within:ring-ring/20 focus-within:border-foreground/30 transition-all">
            <CardContent className="p-2 flex items-center gap-2">
              <Input
                value={followUpText}
                onChange={e => setFollowUpText(e.target.value)}
                placeholder={isFollowUpBusy ? "Checking whether this needs clarification…" : "Follow up — e.g. 'Show this by quarter' or 'Filter to Islamic banks'"}
                disabled={isFollowUpBusy}
                className="border-none bg-transparent shadow-none focus-visible:ring-0 h-9 text-sm"
              />
              <Button type="submit" disabled={!followUpText.trim() || isFollowUpBusy} size="sm" className="gap-1.5 shrink-0">
                <Send className="w-3 h-3" />
                {isFollowUpBusy ? "Checking…" : "Run"}
              </Button>
            </CardContent>
          </Card>
        </form>
      </div>
    </div>
  )
}
