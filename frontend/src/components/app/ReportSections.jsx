import { useState, useMemo } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  ChevronRight, ChevronDown, ChevronUp, ChevronsUpDown,
  Download, ListTodo, CheckCircle2, DollarSign, Activity, Coins,
  TrendingUp, Send, Flame, Eye, ShieldCheck, Sparkles
} from "lucide-react"
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism"
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from "recharts"

// ── Colour palette for charts ─────────────────────────────────────────────────
const CHART_COLORS = ["#18181b", "#52525b", "#16a34a", "#d97706", "#dc2626", "#2563eb", "#7c3aed"]

// ── Chart renderer ────────────────────────────────────────────────────────────
function DataChart({ chart }) {
  if (!chart || !chart.data || chart.data.length === 0) return null

  const tickStyle  = { fontSize: 11, fill: "#71717a", fontFamily: "var(--font-sans)" }
  const tooltipStyle = { fontSize: 12, fontFamily: "var(--font-sans)", border: "1px solid #e4e4e7", borderRadius: 6, boxShadow: "0 2px 8px rgba(0,0,0,.06)" }

  const sharedProps = { data: chart.data, margin: { top: 4, right: 16, left: 0, bottom: 4 } }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-semibold">{chart.title}</CardTitle>
      </CardHeader>
      <CardContent className="pt-0 pb-4">
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
              <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" />
              <XAxis dataKey={chart.x_key} tick={tickStyle} label={{ value: chart.x_label, position: "insideBottom", offset: -2, style: tickStyle }} />
              <YAxis tick={tickStyle} label={{ value: chart.y_label, angle: -90, position: "insideLeft", style: tickStyle }} />
              <Tooltip contentStyle={tooltipStyle} />
              <Line type="monotone" dataKey={chart.y_key} stroke="#18181b" strokeWidth={2} dot={{ r: 3, fill: "#18181b" }} activeDot={{ r: 5 }} />
            </LineChart>
          ) : (
            <BarChart {...sharedProps} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" horizontal={false} />
              <XAxis type="number" tick={tickStyle} label={{ value: chart.y_label, position: "insideBottom", offset: -2, style: tickStyle }} />
              <YAxis dataKey={chart.x_key} type="category" tick={tickStyle} width={140} />
              <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "#f4f4f5" }} />
              <Bar dataKey={chart.y_key} radius={[0, 4, 4, 0]}>
                {chart.data.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
              </Bar>
            </BarChart>
          )}
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

// ── Key findings strip ────────────────────────────────────────────────────────
function KeyFindings({ findings }) {
  if (!findings || findings.length === 0) return null
  return (
    <Card className="border-foreground/10 bg-foreground text-background">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-background/90 flex items-center gap-2">
          <Sparkles className="w-4 h-4" />
          Key Findings
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <ul className="flex flex-col gap-2">
          {findings.map((f, i) => (
            <li key={i} className="flex items-start gap-2.5 text-sm text-background/80 leading-snug">
              <span className="w-5 h-5 rounded-full bg-background/10 flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5 text-background">{i + 1}</span>
              {f}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function ReportSections({ result, query, script, plan = [], taskId, onFollowUp }) {
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

  const summary      = parsed?.summary      || (typeof result === "string" ? result : "Analysis complete.")
  const keyFindings  = parsed?.key_findings || []
  const columns      = parsed?.columns      || []
  const rows         = parsed?.rows         || []
  const chart        = parsed?.chart        || null
  const rawText      = parsed?.raw          || ""
  const hasTableData = columns.length > 0 && rows.length > 0

  const stats = useMemo(() => {
    const rounds = plan.length || 1
    const inp = rounds * 2500, out = rounds * 400
    return { rounds, tokens: inp + out, cost: inp * 0.00000125 + out * 0.000005 }
  }, [plan])

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

  // ── Risk highlights derived from table ──────────────────────────────────────
  const { entityIdx, metricIdx, sortedByMetric } = useMemo(() => {
    if (!hasTableData) return { entityIdx: 0, metricIdx: -1, sortedByMetric: [] }
    let entityIdx = 0
    for (let i = 0; i < columns.length; i++) {
      const c = columns[i].toLowerCase()
      if (["bank","lfi","name","institution","house","exchange","entity"].some(k => c.includes(k))) { entityIdx = i; break }
    }
    let metricIdx = -1
    for (let i = 0; i < columns.length; i++) {
      if (i === entityIdx) continue
      const c = columns[i].toLowerCase()
      if (["score","risk","ratio","amount","volume","count","sum","txs","val","sar"].some(k => c.includes(k))) { metricIdx = i; break }
    }
    if (metricIdx === -1) for (let i = 0; i < columns.length; i++) { if (i !== entityIdx && numericColumnMap[i]) { metricIdx = i; break } }
    const sortedByMetric = [...rows].sort((a, b) => {
      if (metricIdx === -1) return 0
      return (parseFloat(String(b[metricIdx]).replace(/[^0-9.-]/g,""))||0) - (parseFloat(String(a[metricIdx]).replace(/[^0-9.-]/g,""))||0)
    })
    return { entityIdx, metricIdx, sortedByMetric }
  }, [columns, rows, hasTableData, numericColumnMap])

  const highlights = useMemo(() => {
    if (!hasTableData) return []
    const sub = row => metricIdx !== -1 ? `${columns[metricIdx]}: ${row[metricIdx]}` : ""
    const maxVal = parseFloat(String(sortedByMetric[0]?.[metricIdx]).replace(/[^0-9.-]/g,"")) || 1
    const pct    = row => Math.round((parseFloat(String(row?.[metricIdx]).replace(/[^0-9.-]/g,""))||0) / maxVal * 100)
    return [
      { label: "Highest Risk",    row: sortedByMetric[0],                          icon: Flame,      color: "bg-danger" },
      { label: "Watch",           row: sortedByMetric[1] || sortedByMetric[0],     icon: Eye,        color: "bg-warning" },
      { label: "Lowest Exposure", row: sortedByMetric[sortedByMetric.length - 1],  icon: ShieldCheck, color: "bg-zinc-400" },
    ].map(h => ({ ...h, val: h.row?.[entityIdx] || "N/A", sub: sub(h.row || []), pct: pct(h.row || []) }))
  }, [hasTableData, columns, rows, entityIdx, metricIdx, sortedByMetric])

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
      return <Badge variant="outline" className="text-[10px] font-bold uppercase tracking-wider bg-danger/10 text-danger border-danger/30">High</Badge>
    if (["medium","med","warning","watch"].some(k => n.includes(k)))
      return <Badge variant="outline" className="text-[10px] font-bold uppercase tracking-wider bg-warning-bg text-warning border-warning/30">Medium</Badge>
    if (["low","safe","info"].some(k => n.includes(k)))
      return <Badge variant="outline" className="text-[10px] font-bold uppercase tracking-wider bg-success-bg text-success border-success/30">Low</Badge>
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

      {/* ── Key Findings (dark card, top of page) ── */}
      <KeyFindings findings={keyFindings} />

      {/* ── Summary + Risk Highlights ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-semibold">Analysis Summary</CardTitle>
              <div className="w-1.5 h-1.5 rounded-full bg-success" title="Complete" />
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground leading-relaxed">{summary}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold">Risk Highlights</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            {highlights.length === 0 ? (
              <p className="text-xs text-muted-foreground">No table data available.</p>
            ) : (
              <div className="flex flex-col gap-3">
                {highlights.map((h, i) => {
                  const Icon = h.icon
                  return (
                    <div key={i}>
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2">
                          <Icon className="w-3.5 h-3.5 text-muted-foreground" />
                          <span className="text-xs text-muted-foreground font-medium">{h.label}</span>
                        </div>
                        <span className="text-xs font-semibold text-foreground truncate max-w-[100px]">{h.val}</span>
                      </div>
                      <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
                        <div className={`h-full rounded-full transition-all duration-700 ${h.color}`} style={{ width: `${h.pct}%` }} />
                      </div>
                      {h.sub && <p className="text-[10px] text-muted-foreground mt-1 truncate">{h.sub}</p>}
                      {i < highlights.length - 1 && <Separator className="mt-3" />}
                    </div>
                  )
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ── Chart ── */}
      {chart && <DataChart chart={chart} />}

      {/* ── Data Table ── */}
      {hasTableData && (
        <Card>
          <CardHeader className="pb-0">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-sm font-semibold">Results</CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">{rows.length} records · {columns.length} columns</p>
              </div>
              <Button variant="outline" size="sm" onClick={exportCSV} className="gap-1.5 h-7 text-xs">
                <Download className="w-3.5 h-3.5" />
                Export CSV
              </Button>
            </div>
          </CardHeader>

          <CardContent className="p-0 mt-3">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/40 hover:bg-muted/40 border-y border-border">
                    <TableHead className="w-10 px-4 py-2.5 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">#</TableHead>
                    {columns.map((col, idx) => {
                      const isSorted = sortCol === idx
                      const isNum    = numericColumnMap[idx]
                      return (
                        <TableHead
                          key={idx}
                          onClick={() => handleSort(idx)}
                          className={`px-4 py-2.5 text-[10px] font-bold uppercase tracking-widest text-muted-foreground cursor-pointer hover:text-foreground select-none transition-colors ${isNum ? "text-right" : "text-left"} ${isSorted ? "text-foreground" : ""}`}
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
                    <TableRow key={i} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                      <TableCell className="px-4 py-3 w-10 font-mono text-[11px] text-muted-foreground font-medium">{i + 1}</TableCell>
                      {row.map((cell, ci) => {
                        if (ci === riskColIdx) return <TableCell key={ci} className="px-4 py-3">{renderBadge(cell)}</TableCell>
                        if (ci === 0) return <TableCell key={ci} className="px-4 py-3 text-sm font-semibold text-foreground">{cell}</TableCell>
                        if (numericColumnMap[ci]) {
                          const val = parseFloat(String(cell).replace(/[^0-9.-]/g,"")) || 0
                          const pct = Math.round(val / (columnMaxValues[ci] || 1) * 100)
                          return (
                            <TableCell key={ci} className="px-4 py-3 text-right">
                              <p className="font-mono text-sm font-semibold text-foreground tabular-nums">{typeof cell === "number" ? cell.toLocaleString() : cell}</p>
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
          </CardContent>
        </Card>
      )}

      {/* Raw text fallback */}
      {!hasTableData && rawText && (
        <Card>
          <CardContent className="p-5 font-mono text-xs text-muted-foreground leading-relaxed overflow-x-auto">{rawText}</CardContent>
        </Card>
      )}

      {/* ── Collapsible: Supervisory Plan ── */}
      {plan && plan.length > 0 && (
        <Card>
          <button
            onClick={() => setShowPlan(v => !v)}
            className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-muted/30 transition-colors cursor-pointer rounded-lg"
          >
            <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
              {showPlan ? <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" /> : <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />}
              <ListTodo className="w-4 h-4 text-muted-foreground" />
              Supervisory Plan
            </span>
            <Badge variant="secondary" className="text-[10px]">{plan.length} steps</Badge>
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
          <span className="text-[11px] text-muted-foreground font-mono">
            {stats.rounds}R · {stats.tokens.toLocaleString()} tok · ${stats.cost.toFixed(4)}
          </span>
        </button>

        {showAudit && (
          <>
            <Separator />
            <div className="grid grid-cols-2 md:grid-cols-4 gap-0 divide-x divide-border border-b border-border">
              {[
                { label: "Analysis Rounds", value: stats.rounds.toString(),       unit: stats.rounds === 1 ? "iteration" : "iterations", icon: Activity   },
                { label: "Tokens Used",     value: stats.tokens.toLocaleString(), unit: "total tokens",                                   icon: Coins      },
                { label: "Model Cost",      value: `$${stats.cost.toFixed(4)}`,   unit: "estimated",                                      icon: DollarSign },
                { label: "Data Rows",       value: hasTableData ? rows.length.toString() : "—", unit: hasTableData ? `${columns.length} columns` : "no table data", icon: TrendingUp },
              ].map(({ label, value, unit, icon: Icon }) => (
                <div key={label} className="flex items-start gap-3 px-5 py-4">
                  <div className="w-7 h-7 rounded-md border border-border flex items-center justify-center text-muted-foreground shrink-0">
                    <Icon className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <p className="text-[10px] text-muted-foreground font-medium">{label}</p>
                    <p className="text-base font-bold text-foreground leading-tight">{value}</p>
                    <p className="text-[10px] text-muted-foreground">{unit}</p>
                  </div>
                </div>
              ))}
            </div>

            <button
              onClick={() => setShowCode(v => !v)}
              className="w-full flex items-center justify-between px-5 py-3 hover:bg-muted/30 transition-colors cursor-pointer"
            >
              <span className="flex items-center gap-2 text-sm text-muted-foreground font-medium">
                {showCode ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                Python Script
              </span>
              <Badge variant="secondary" className="font-mono text-[10px]">.py</Badge>
            </button>
            {showCode && (
              <>
                <Separator />
                <SyntaxHighlighter
                  language="python"
                  style={oneLight}
                  customStyle={{ background: '#fafafa', padding: '16px', margin: 0, fontSize: '12px', lineHeight: '1.6', fontFamily: "'Source Code Pro', monospace", borderRadius: '0 0 0.5rem 0.5rem' }}
                >
                  {script || "# No code executed."}
                </SyntaxHighlighter>
              </>
            )}
          </>
        )}
      </Card>

      {/* ── Follow-up bar ── */}
      <div className="sticky bottom-0 -mx-6 px-6 pb-4 pt-4 bg-gradient-to-t from-background via-background/95 to-transparent z-30">
        <form onSubmit={handleSubmit}>
          <Card className="shadow-md border-border focus-within:ring-2 focus-within:ring-ring/20 focus-within:border-foreground/30 transition-all">
            <CardContent className="p-2 flex items-center gap-2">
              <Input
                value={followUpText}
                onChange={e => setFollowUpText(e.target.value)}
                placeholder="Follow up — e.g. 'Show this by quarter' or 'Filter to Islamic banks'"
                className="border-none bg-transparent shadow-none focus-visible:ring-0 h-9 text-sm"
              />
              <Button type="submit" disabled={!followUpText.trim()} size="sm" className="gap-1.5 shrink-0">
                <Send className="w-3 h-3" />
                Run
              </Button>
            </CardContent>
          </Card>
        </form>
      </div>
    </div>
  )
}
