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
  AlertTriangle, TrendingUp, TrendingDown, Send, Flame, Eye, Shield
} from "lucide-react"
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism"

export default function ReportSections({ result, query, script, plan = [], taskId, onFollowUp }) {
  const [showCode, setShowCode] = useState(false)
  const [followUpText, setFollowUpText] = useState("")
  const [sortCol, setSortCol] = useState(null)
  const [sortDir, setSortDir] = useState("desc")

  const parsed = useMemo(() => {
    if (!result) return null
    try {
      let s = typeof result === "string" ? result.trim() : JSON.stringify(result)
      if (s.startsWith("```json")) s = s.replace(/^```json/, "").replace(/```$/, "")
      else if (s.startsWith("```")) s = s.replace(/^```/, "").replace(/```$/, "")
      return JSON.parse(s.trim())
    } catch { return null }
  }, [result])

  const summary      = parsed?.summary || (typeof result === "string" ? result : "Analysis complete.")
  const columns      = parsed?.columns || []
  const rows         = parsed?.rows    || []
  const rawText      = parsed?.raw     || ""
  const hasTableData = columns.length > 0 && rows.length > 0

  const stats = useMemo(() => {
    const rounds = plan.length || 1
    const inp = rounds * 2500, out = rounds * 400
    return { rounds, tokens: inp + out, cost: inp * 0.00000125 + out * 0.000005 }
  }, [plan])

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

  const highlights = useMemo(() => {
    const noData = [
      { label: "Highest Risk", val: "None", sub: "No data", icon: Flame,      accent: "border-t-red-500",   textColor: "text-red-600",    bg: "bg-red-050"   },
      { label: "Watch",        val: "None", sub: "No data", icon: Eye,        accent: "border-t-amber-500", textColor: "text-amber-600",  bg: "bg-amber-50"  },
      { label: "Lowest",       val: "None", sub: "No data", icon: Shield,     accent: "border-t-slate-400", textColor: "text-slate-500",  bg: "bg-muted"     },
    ]
    if (!hasTableData) return noData

    let entityIdx = 0
    for (let i = 0; i < columns.length; i++) {
      const c = columns[i].toLowerCase()
      if (["bank","lfi","name","institution","house","exchange","entity"].some(k => c.includes(k))) { entityIdx = i; break }
    }

    let metricIdx = -1
    for (let i = 0; i < columns.length; i++) {
      if (i === entityIdx) continue
      const c = columns[i].toLowerCase()
      if (["score","risk","ratio","amount","volume","count","sum","txs","val"].some(k => c.includes(k))) { metricIdx = i; break }
    }
    if (metricIdx === -1) {
      for (let i = 0; i < columns.length; i++) {
        if (i !== entityIdx && numericColumnMap[i]) { metricIdx = i; break }
      }
    }

    let sorted = [...rows]
    if (metricIdx !== -1) sorted.sort((a, b) => (parseFloat(String(b[metricIdx]).replace(/[^0-9.-]/g,""))||0) - (parseFloat(String(a[metricIdx]).replace(/[^0-9.-]/g,""))||0))

    const sub = row => metricIdx !== -1 ? `${columns[metricIdx]}: ${Number(row[metricIdx]).toLocaleString()}` : (columns[1] ? `${columns[1]}: ${row[1]}` : "Matched LFI")
    const maxVal = parseFloat(String(sorted[0]?.[metricIdx]).replace(/[^0-9.-]/g,"")) || 1
    const pct = row => { if (metricIdx === -1) return 100; return Math.round((parseFloat(String(row[metricIdx]).replace(/[^0-9.-]/g,""))||0) / maxVal * 100) }

    return [
      { label: "Highest Risk", val: sorted[0]?.[entityIdx] || "N/A", sub: sub(sorted[0]||[]), pct: pct(sorted[0]||[]), icon: Flame,  accent: "border-t-red-500",   textColor: "text-red-600",   bg: "bg-red-050"  },
      { label: "Watch",        val: sorted[1]?.[entityIdx] || "N/A", sub: sub(sorted[1]||sorted[0]||[]), pct: pct(sorted[1]||sorted[0]||[]), icon: Eye, accent: "border-t-amber-500", textColor: "text-amber-600", bg: "bg-amber-50" },
      { label: "Lowest",       val: sorted[sorted.length-1]?.[entityIdx] || "N/A", sub: sub(sorted[sorted.length-1]||[]), pct: pct(sorted[sorted.length-1]||[]), icon: TrendingDown, accent: "border-t-slate-400", textColor: "text-slate-500", bg: "bg-muted" },
    ]
  }, [columns, rows, hasTableData, numericColumnMap])

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
    if (["high","danger","critical"].some(k => n.includes(k))) return <Badge variant="destructive" className="text-[10px] rounded-md font-bold tracking-wider uppercase">High</Badge>
    if (["medium","med","warning","watch"].some(k => n.includes(k))) return <Badge variant="outline" className="text-[10px] rounded-md font-bold tracking-wider uppercase border-amber-300 bg-amber-100 text-amber-700">Medium</Badge>
    if (["low","safe","info"].some(k => n.includes(k))) return <Badge variant="outline" className="text-[10px] rounded-md font-bold tracking-wider uppercase border-green-300 bg-green-100 text-green-700">Low</Badge>
    return val
  }

  const exportCSV = () => {
    if (!hasTableData) return
    const lines = [columns.map(c => `"${String(c).replace(/"/g,'""')}"`).join(','), ...rows.map(r => r.map(c => `"${String(c).replace(/"/g,'""')}"`).join(','))]
    const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(new Blob([lines.join('\n')], {type:'text/csv'})), download: `ds_star_${Date.now()}.csv`, style: 'visibility:hidden' })
    document.body.appendChild(a); a.click(); document.body.removeChild(a)
  }

  const handleFollowUpSubmit = e => { e.preventDefault(); if (!followUpText.trim()) return; onFollowUp(followUpText); setFollowUpText("") }

  return (
    <div className="flex flex-col gap-5 pb-28 w-full">

      {/* ── 1. Summary — dark hero card ── */}
      <Card className="bg-slate-900 border-slate-800 text-white overflow-hidden relative">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent" />
        <div className="absolute -top-10 -right-10 w-32 h-32 rounded-full bg-primary/15 blur-2xl pointer-events-none" />
        <CardHeader className="pb-2">
          <div className="flex items-center gap-2">
            <div className="w-1 h-4 rounded-full bg-primary" />
            <CardTitle className="text-[10px] font-bold uppercase tracking-[0.18em] text-primary/80">
              Analysis Summary
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-[15px] text-slate-200 leading-[1.75] font-medium">{summary}</p>
        </CardContent>
      </Card>

      {/* ── 2. Metrics ── */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { icon: Activity,   label: "Analysis Rounds",  value: stats.rounds.toString(), unit: "iterations",  iconClass: "text-blue-600",  bgClass: "bg-blue-100"  },
          { icon: Coins,      label: "Tokens Used",      value: stats.tokens.toLocaleString(), unit: "total",  iconClass: "text-amber-600", bgClass: "bg-amber-100" },
          { icon: DollarSign, label: "Model Cost",       value: `$${stats.cost.toFixed(4)}`,   unit: "estimated", iconClass: "text-green-700", bgClass: "bg-green-100" },
        ].map(({ icon: Icon, label, value, unit, iconClass, bgClass }) => (
          <Card key={label} className="shadow-sm">
            <CardContent className="p-4">
              <div className={`w-8 h-8 rounded-lg ${bgClass} flex items-center justify-center mb-3`}>
                <Icon className={`w-4 h-4 ${iconClass}`} />
              </div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-1">{label}</p>
              <p className="text-[22px] font-extrabold text-foreground leading-none tracking-tight">{value}</p>
              <p className="text-[11px] text-muted-foreground mt-0.5">{unit}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {hasTableData && (<>

        {/* ── 3. Highlights ── */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {highlights.map((h, i) => {
            const Icon = h.icon
            return (
              <Card key={i} className={`border-t-[3px] ${h.accent} shadow-sm overflow-hidden`}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between mb-3">
                    <span className={`text-[10px] font-bold uppercase tracking-[0.15em] ${h.textColor}`}>{h.label}</span>
                    <div className={`w-7 h-7 rounded-lg ${h.bg} flex items-center justify-center`}>
                      <Icon className={`w-3.5 h-3.5 ${h.textColor}`} />
                    </div>
                  </div>
                  <p className="text-[18px] font-extrabold text-foreground leading-tight truncate mb-0.5">{h.val}</p>
                  <p className="text-[11px] text-muted-foreground mb-3 truncate">{h.sub}</p>
                  {h.pct !== undefined && (
                    <div className="h-1 w-full bg-muted rounded-full overflow-hidden">
                      <div className="h-full rounded-full bg-primary transition-all duration-700" style={{ width: `${h.pct}%`, opacity: 0.7 + (h.pct / 300) }} />
                    </div>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>

        {/* ── 4. Plan ── */}
        {plan && plan.length > 0 && (
          <Card className="shadow-sm">
            <CardHeader>
              <CardTitle className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground flex items-center gap-2">
                <ListTodo className="w-3.5 h-3.5 text-primary" />
                Supervisory Plan Workflow
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="flex flex-col">
                {plan.map((step, idx) => (
                  <div key={idx} className="flex items-start gap-3 py-2.5 border-b border-border last:border-none">
                    <div className="w-5 h-5 rounded-full bg-green-100 border border-green-300 flex items-center justify-center shrink-0 mt-0.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-green-600" />
                    </div>
                    <p className="text-sm text-muted-foreground leading-snug">
                      <span className="font-bold text-foreground mr-1.5">Step {idx + 1}.</span>{step}
                    </p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* ── 5. Data Table ── */}
        <Card className="shadow-sm overflow-hidden">
          {/* Toolbar — dark header */}
          <div className="flex items-center justify-between px-4 py-3 bg-slate-900 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="font-mono text-[11px] border-slate-700 bg-slate-800 text-slate-400">
                {rows.length} rows
              </Badge>
              <span className="text-[10px] text-slate-600">· click headers to sort</span>
            </div>
            <Button variant="ghost" size="sm" onClick={exportCSV} className="text-slate-400 hover:text-white hover:bg-slate-800 gap-1.5">
              <Download className="w-3.5 h-3.5" />
              Export CSV
            </Button>
          </div>

          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/50 hover:bg-muted/50 border-b-2 border-border">
                  <TableHead className="w-10 px-4 text-[9px] font-black uppercase tracking-widest text-muted-foreground">#</TableHead>
                  {columns.map((col, idx) => {
                    const sorted = sortCol === idx
                    const num = numericColumnMap[idx]
                    return (
                      <TableHead
                        key={idx}
                        onClick={() => handleSort(idx)}
                        className={`px-4 text-[9px] font-black uppercase tracking-widest text-muted-foreground cursor-pointer hover:text-foreground hover:bg-muted transition-colors select-none ${num ? "text-right" : "text-left"} ${sorted ? "text-foreground bg-muted" : ""}`}
                      >
                        <span className={`flex items-center gap-1 ${num ? "justify-end" : ""}`}>
                          {col}
                          {sorted
                            ? sortDir === "asc" ? <ChevronUp className="w-3 h-3 text-primary" /> : <ChevronDown className="w-3 h-3 text-primary" />
                            : <ChevronsUpDown className="w-3 h-3 opacity-25" />}
                        </span>
                      </TableHead>
                    )
                  })}
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedRows.map((row, i) => (
                  <TableRow key={i} className={`border-b border-border/50 hover:bg-crimson-050/40 transition-colors ${i % 2 === 1 ? "bg-muted/30" : ""}`}>
                    <TableCell className="px-4 py-3 w-10 font-mono text-[11px] font-bold text-muted-foreground tabular-nums">{i + 1}</TableCell>
                    {row.map((cell, ci) => {
                      if (ci === riskColIdx) return <TableCell key={ci} className="px-4 py-3">{renderBadge(cell)}</TableCell>
                      if (ci === 0) return <TableCell key={ci} className="px-4 py-3 font-bold text-foreground text-sm">{cell}</TableCell>
                      if (numericColumnMap[ci]) {
                        const val = parseFloat(String(cell).replace(/[^0-9.-]/g,"")) || 0
                        const pct = Math.round(val / (columnMaxValues[ci] || 1) * 100)
                        return (
                          <TableCell key={ci} className="px-4 py-2.5 text-right">
                            <span className="font-mono text-sm font-semibold text-foreground tabular-nums block">{typeof cell === "number" ? cell.toLocaleString() : cell}</span>
                            <div className="w-16 h-1 bg-muted rounded-full overflow-hidden ml-auto mt-1">
                              <div className="h-full bg-primary/60 rounded-full transition-all" style={{ width: `${pct}%` }} />
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
        </Card>
      </>)}

      {/* Raw fallback */}
      {!hasTableData && rawText && (
        <Card className="shadow-sm">
          <CardContent className="p-5 font-mono text-xs text-muted-foreground leading-relaxed overflow-x-auto">{rawText}</CardContent>
        </Card>
      )}

      {/* ── 6. Python Script ── */}
      <Card className="shadow-sm overflow-hidden">
        <button onClick={() => setShowCode(v => !v)} className="w-full flex items-center justify-between px-4 py-3 hover:bg-muted/50 transition-colors cursor-pointer">
          <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
            {showCode ? <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" /> : <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />}
            View Python script
          </span>
          <Badge variant="secondary" className="font-mono text-[10px] uppercase tracking-wider">.py</Badge>
        </button>
        {showCode && (
          <>
            <Separator />
            <SyntaxHighlighter
              language="python"
              style={oneDark}
              customStyle={{ background: '#1A1F2E', padding: '16px', margin: 0, fontSize: '12px', lineHeight: '1.6', fontFamily: "'Source Code Pro', monospace", borderRadius: 0 }}
            >
              {script || "# No code executed."}
            </SyntaxHighlighter>
          </>
        )}
      </Card>

      {/* ── 7. Follow-up Bar ── */}
      <div className="sticky bottom-0 -mx-6 px-6 pb-4 pt-4 bg-gradient-to-t from-background via-background/95 to-transparent z-30">
        <form onSubmit={handleFollowUpSubmit}>
          <Card className="shadow-md border-border focus-within:ring-2 focus-within:ring-ring/30 focus-within:border-primary/50 transition-all">
            <CardContent className="p-2 flex items-center gap-2">
              <Input
                value={followUpText}
                onChange={e => setFollowUpText(e.target.value)}
                placeholder="Follow up — e.g. 'Show this by quarter' or 'Filter to Islamic banks only'"
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
