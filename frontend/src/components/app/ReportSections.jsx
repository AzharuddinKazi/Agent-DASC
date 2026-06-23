import { useState, useMemo } from "react"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../ui/table"
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

  const summary = parsed?.summary || (typeof result === "string" ? result : "Analysis complete.")
  const columns = parsed?.columns || []
  const rows = parsed?.rows || []
  const rawText = parsed?.raw || ""
  const hasTableData = columns.length > 0 && rows.length > 0

  const stats = useMemo(() => {
    const rounds = plan.length || 1
    const estInputTokens = rounds * 2500
    const estOutputTokens = rounds * 400
    const estCost = (estInputTokens * 0.00000125) + (estOutputTokens * 0.000005)
    return { rounds, tokens: estInputTokens + estOutputTokens, cost: estCost }
  }, [plan])

  const numericColumnMap = useMemo(() => {
    const map = {}
    if (!hasTableData) return map
    for (let colIdx = 0; colIdx < columns.length; colIdx++) {
      let isNumeric = true, checks = 0
      for (let r = 0; r < Math.min(rows.length, 10); r++) {
        const cell = rows[r][colIdx]
        if (cell === undefined || cell === null || cell === "") continue
        checks++
        if (isNaN(parseFloat(String(cell).replace(/[^0-9.-]/g, "")))) { isNumeric = false; break }
      }
      map[colIdx] = isNumeric && checks > 0
    }
    return map
  }, [columns, rows, hasTableData])

  // Max values per numeric column for inline bar rendering
  const columnMaxValues = useMemo(() => {
    const maxMap = {}
    if (!hasTableData) return maxMap
    for (let colIdx = 0; colIdx < columns.length; colIdx++) {
      if (!numericColumnMap[colIdx]) continue
      let max = 0
      for (const row of rows) {
        const val = parseFloat(String(row[colIdx]).replace(/[^0-9.-]/g, "")) || 0
        if (val > max) max = val
      }
      maxMap[colIdx] = max
    }
    return maxMap
  }, [columns, rows, hasTableData, numericColumnMap])

  const highlights = useMemo(() => {
    const noData = [
      { label: "Highest Risk", val: "None", sub: "No data", icon: Flame, accentClass: "from-red-500 to-red-700", textColor: "text-red-600", bgColor: "bg-red-050" },
      { label: "Watch", val: "None", sub: "No data", icon: Eye, accentClass: "from-amber-400 to-amber-600", textColor: "text-amber-600", bgColor: "bg-amber-50" },
      { label: "Lowest Exposure", val: "None", sub: "No data", icon: Shield, accentClass: "from-slate-400 to-slate-600", textColor: "text-slate-500", bgColor: "bg-slate-050" },
    ]
    if (!hasTableData) return noData

    let entityIdx = 0
    for (let i = 0; i < columns.length; i++) {
      const c = columns[i].toLowerCase()
      if (c.includes("bank") || c.includes("lfi") || c.includes("name") || c.includes("institution") || c.includes("house") || c.includes("exchange") || c.includes("entity")) {
        entityIdx = i; break
      }
    }

    let metricIdx = -1
    for (let i = 0; i < columns.length; i++) {
      if (i === entityIdx) continue
      const c = columns[i].toLowerCase()
      if (c.includes("score") || c.includes("risk") || c.includes("ratio") || c.includes("amount") || c.includes("volume") || c.includes("count") || c.includes("sum") || c.includes("txs") || c.includes("val")) {
        metricIdx = i; break
      }
    }
    if (metricIdx === -1) {
      for (let i = 0; i < columns.length; i++) {
        if (i !== entityIdx && numericColumnMap[i]) { metricIdx = i; break }
      }
    }

    let sorted = [...rows]
    if (metricIdx !== -1) {
      sorted.sort((a, b) => {
        const va = parseFloat(String(a[metricIdx]).replace(/[^0-9.-]/g, "")) || 0
        const vb = parseFloat(String(b[metricIdx]).replace(/[^0-9.-]/g, "")) || 0
        return vb - va
      })
    }

    const getSubtext = (row) => metricIdx !== -1
      ? `${columns[metricIdx]}: ${Number(row[metricIdx]).toLocaleString()}`
      : columns[1] ? `${columns[1]}: ${row[1]}` : "Matched LFI"

    const maxVal = metricIdx !== -1
      ? parseFloat(String(sorted[0]?.[metricIdx]).replace(/[^0-9.-]/g, "")) || 1
      : 1

    const getPct = (row) => {
      if (metricIdx === -1) return 100
      const v = parseFloat(String(row[metricIdx]).replace(/[^0-9.-]/g, "")) || 0
      return Math.round((v / maxVal) * 100)
    }

    return [
      { label: "Highest Risk", val: sorted[0]?.[entityIdx] || "N/A", sub: getSubtext(sorted[0] || []), pct: getPct(sorted[0] || []), icon: Flame, accentClass: "from-red-500 to-red-700", textColor: "text-red-600", bgColor: "bg-red-050" },
      { label: "Watch", val: sorted[1]?.[entityIdx] || "N/A", sub: getSubtext(sorted[1] || sorted[0] || []), pct: getPct(sorted[1] || sorted[0] || []), icon: Eye, accentClass: "from-amber-400 to-amber-600", textColor: "text-amber-600", bgColor: "bg-amber-50" },
      { label: "Lowest Exposure", val: sorted[sorted.length - 1]?.[entityIdx] || "N/A", sub: getSubtext(sorted[sorted.length - 1] || []), pct: getPct(sorted[sorted.length - 1] || []), icon: Shield, accentClass: "from-slate-400 to-slate-600", textColor: "text-slate-500", bgColor: "bg-slate-050" },
    ]
  }, [columns, rows, hasTableData, numericColumnMap])

  const handleSort = (colIdx) => {
    if (sortCol === colIdx) setSortDir(d => d === "asc" ? "desc" : "asc")
    else { setSortCol(colIdx); setSortDir("desc") }
  }

  const sortedDisplayRows = useMemo(() => {
    if (!hasTableData) return []
    let list = [...rows]
    if (sortCol !== null) {
      list.sort((a, b) => {
        const na = parseFloat(String(a[sortCol]).replace(/[^0-9.-]/g, ""))
        const nb = parseFloat(String(b[sortCol]).replace(/[^0-9.-]/g, ""))
        if (!isNaN(na) && !isNaN(nb)) return sortDir === "asc" ? na - nb : nb - na
        return sortDir === "asc"
          ? String(a[sortCol]).localeCompare(String(b[sortCol]))
          : String(b[sortCol]).localeCompare(String(a[sortCol]))
      })
    }
    return list
  }, [rows, sortCol, sortDir, hasTableData])

  const riskColIdx = useMemo(() => columns.findIndex(col => {
    const c = col.toLowerCase()
    return c.includes("risk") || c.includes("level") || c.includes("alert") || c.includes("class")
  }), [columns])

  const renderCellBadge = (val) => {
    const n = String(val).trim().toLowerCase()
    if (n.includes("high") || n.includes("danger") || n.includes("critical"))
      return <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold tracking-wider uppercase bg-red-100 text-red-600 border border-red-200">High</span>
    if (n.includes("medium") || n.includes("med") || n.includes("warning") || n.includes("watch"))
      return <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold tracking-wider uppercase bg-amber-100 text-amber-700 border border-amber-200">Medium</span>
    if (n.includes("low") || n.includes("safe") || n.includes("info"))
      return <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold tracking-wider uppercase bg-green-100 text-green-700 border border-green-200">Low</span>
    return val
  }

  const handleExportCSV = () => {
    if (!hasTableData) return
    const lines = [
      columns.map(c => `"${String(c).replace(/"/g, '""')}"`).join(','),
      ...rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(','))
    ]
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `ds_star_${Date.now()}.csv`; a.style.visibility = 'hidden'
    document.body.appendChild(a); a.click(); document.body.removeChild(a)
  }

  const handleRunFollowUp = (e) => {
    e.preventDefault()
    if (!followUpText.trim()) return
    onFollowUp(followUpText)
    setFollowUpText("")
  }

  return (
    <div className="flex flex-col gap-5 pb-28 font-sans w-full">

      {/* ── 1. Summary — dark hero card ── */}
      <div className="relative bg-slate-900 rounded-xl p-6 overflow-hidden shadow-card-md">
        {/* Subtle crimson gradient glow top-right */}
        <div className="absolute -top-12 -right-12 w-40 h-40 rounded-full bg-crimson-600/20 blur-2xl pointer-events-none" />
        <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-crimson-500/40 to-transparent" />

        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-1 h-4 rounded-full bg-gradient-to-b from-crimson-400 to-crimson-600" />
            <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-crimson-400">
              Analysis Summary
            </span>
          </div>
          <p className="text-[15px] text-slate-200 leading-[1.75] font-medium">
            {summary}
          </p>
        </div>
      </div>

      {/* ── 2. Metrics Row ── */}
      <div className="grid grid-cols-3 gap-3">
        {[
          {
            icon: Activity, label: "Analysis Rounds",
            value: stats.rounds.toString(), unit: stats.rounds === 1 ? "iteration" : "iterations",
            gradient: "from-blue-500/10 to-blue-600/5", iconBg: "bg-blue-100", iconColor: "text-blue-600",
            border: "border-blue-100"
          },
          {
            icon: Coins, label: "Tokens Used",
            value: stats.tokens.toLocaleString(), unit: "total",
            gradient: "from-amber-500/10 to-amber-600/5", iconBg: "bg-amber-100", iconColor: "text-amber-600",
            border: "border-amber-100"
          },
          {
            icon: DollarSign, label: "Model Cost",
            value: `$${stats.cost.toFixed(4)}`, unit: "estimated",
            gradient: "from-green-500/10 to-green-600/5", iconBg: "bg-green-100", iconColor: "text-green-700",
            border: "border-green-100"
          },
        ].map(({ icon: Icon, label, value, unit, gradient, iconBg, iconColor, border }) => (
          <div key={label} className={`relative bg-gradient-to-br ${gradient} border ${border} rounded-xl p-4 shadow-card overflow-hidden`}>
            <div className={`w-8 h-8 rounded-lg ${iconBg} flex items-center justify-center mb-3`}>
              <Icon className={`w-4 h-4 ${iconColor}`} />
            </div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">{label}</div>
            <div className="text-[22px] font-extrabold text-slate-900 leading-none tracking-tight">{value}</div>
            <div className="text-[11px] text-slate-400 mt-0.5 font-medium">{unit}</div>
          </div>
        ))}
      </div>

      {hasTableData && (
        <>
          {/* ── 3. Highlight Cards ── */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {highlights.map((c, idx) => {
              const Icon = c.icon
              return (
                <div key={idx} className="bg-surface-base border border-slate-100 rounded-xl overflow-hidden shadow-card">
                  {/* Gradient top strip */}
                  <div className={`h-1.5 bg-gradient-to-r ${c.accentClass} w-full`} />
                  <div className="p-4">
                    <div className="flex items-center justify-between mb-3">
                      <span className={`text-[10px] font-bold uppercase tracking-[0.15em] ${c.textColor}`}>
                        {c.label}
                      </span>
                      <div className={`w-7 h-7 rounded-lg ${c.bgColor} flex items-center justify-center`}>
                        <Icon className={`w-3.5 h-3.5 ${c.textColor}`} />
                      </div>
                    </div>
                    <div className="text-[18px] font-extrabold text-slate-900 leading-tight tracking-tight mb-1 truncate">
                      {c.val}
                    </div>
                    <div className="text-[11px] text-slate-400 mb-3 truncate">{c.sub}</div>
                    {/* Proportional bar */}
                    {c.pct !== undefined && (
                      <div className="h-1 w-full bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full bg-gradient-to-r ${c.accentClass} transition-all duration-700`}
                          style={{ width: `${c.pct}%` }}
                        />
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          {/* ── 4. Supervisory Plan ── */}
          {plan && plan.length > 0 && (
            <div className="bg-surface-base border border-slate-100 rounded-xl p-5 shadow-card">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-6 h-6 rounded-md bg-crimson-050 flex items-center justify-center">
                  <ListTodo className="w-3.5 h-3.5 text-crimson-600" />
                </div>
                <h3 className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
                  Supervisory Plan Workflow
                </h3>
              </div>
              <div className="flex flex-col gap-0">
                {plan.map((step, idx) => (
                  <div key={idx} className="flex items-start gap-3 py-2.5 border-b border-slate-050 last:border-none">
                    <div className="flex items-center justify-center w-5 h-5 rounded-full bg-green-100 border border-green-300 shrink-0 mt-0.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-green-600" />
                    </div>
                    <div className="flex-1 text-[13px] text-slate-600 leading-snug">
                      <span className="font-bold text-slate-800 mr-1.5">Step {idx + 1}.</span>
                      {step}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── 5. Data Table ── */}
          <div className="bg-surface-base border border-slate-100 rounded-xl overflow-hidden shadow-card">
            {/* Toolbar */}
            <div className="flex items-center justify-between px-4 py-3 bg-slate-900 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[11px] font-bold text-slate-400 bg-slate-800 px-2 py-0.5 rounded border border-slate-700">
                  {rows.length} rows
                </span>
                <span className="text-[10px] text-slate-600">Click column headers to sort</span>
              </div>
              <button
                onClick={handleExportCSV}
                className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-400 hover:text-white px-3 py-1.5 rounded-lg hover:bg-slate-800 border border-transparent hover:border-slate-700 transition-all cursor-pointer"
              >
                <Download className="w-3.5 h-3.5" />
                Export CSV
              </button>
            </div>

            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent border-b-2 border-slate-100">
                    <TableHead className="text-[9px] font-black text-slate-400 uppercase tracking-widest w-10 h-10 px-4 bg-slate-050/80">
                      #
                    </TableHead>
                    {columns.map((col, idx) => {
                      const isSorted = sortCol === idx
                      const isNumeric = numericColumnMap[idx]
                      return (
                        <TableHead
                          key={idx}
                          onClick={() => handleSort(idx)}
                          className={`text-[9px] font-black text-slate-400 uppercase tracking-widest h-10 px-4 cursor-pointer hover:text-slate-700 hover:bg-slate-050 transition-colors select-none bg-slate-050/80 ${
                            isNumeric ? "text-right" : "text-left"
                          } ${isSorted ? "text-slate-800 bg-slate-100" : ""}`}
                        >
                          <div className={`flex items-center gap-1 ${isNumeric ? "justify-end" : "justify-start"}`}>
                            {col}
                            {isSorted
                              ? sortDir === "asc"
                                ? <ChevronUp className="w-3 h-3 text-crimson-600" />
                                : <ChevronDown className="w-3 h-3 text-crimson-600" />
                              : <ChevronsUpDown className="w-3 h-3 opacity-25" />
                            }
                          </div>
                        </TableHead>
                      )
                    })}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedDisplayRows.map((row, i) => (
                    <TableRow
                      key={i}
                      className={`hover:bg-crimson-050/40 transition-colors border-b border-slate-050 ${
                        i % 2 === 1 ? "bg-slate-050/40" : ""
                      }`}
                    >
                      <TableCell className="font-mono text-[11px] text-slate-400 px-4 py-3 w-10 font-bold tabular-nums">
                        {i + 1}
                      </TableCell>
                      {row.map((cell, colIdx) => {
                        const isNumeric = numericColumnMap[colIdx]
                        const isRisk = colIdx === riskColIdx

                        if (isRisk) {
                          return <TableCell key={colIdx} className="px-4 py-3">{renderCellBadge(cell)}</TableCell>
                        }

                        if (colIdx === 0) {
                          return (
                            <TableCell key={colIdx} className="font-bold text-slate-900 text-[13px] px-4 py-3">
                              {cell}
                            </TableCell>
                          )
                        }

                        if (isNumeric) {
                          const val = parseFloat(String(cell).replace(/[^0-9.-]/g, "")) || 0
                          const max = columnMaxValues[colIdx] || 1
                          const pct = Math.round((val / max) * 100)
                          return (
                            <TableCell key={colIdx} className="px-4 py-2.5 text-right">
                              <div className="flex flex-col items-end gap-1">
                                <span className="font-mono text-[13px] font-semibold text-slate-900 tabular-nums">
                                  {typeof cell === "number" ? cell.toLocaleString() : cell}
                                </span>
                                {/* Inline mini bar */}
                                <div className="w-16 h-1 bg-slate-100 rounded-full overflow-hidden">
                                  <div
                                    className="h-full rounded-full bg-gradient-to-r from-crimson-400 to-crimson-600 transition-all duration-500"
                                    style={{ width: `${pct}%` }}
                                  />
                                </div>
                              </div>
                            </TableCell>
                          )
                        }

                        return (
                          <TableCell key={colIdx} className="text-[13px] text-slate-600 px-4 py-3">
                            {cell}
                          </TableCell>
                        )
                      })}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        </>
      )}

      {/* Raw fallback */}
      {!hasTableData && rawText && (
        <div className="bg-surface-base border border-slate-100 rounded-xl p-5 shadow-card font-mono text-[12px] text-slate-600 leading-relaxed overflow-x-auto">
          {rawText}
        </div>
      )}

      {/* ── 6. Python Script ── */}
      <div className="border border-slate-200 rounded-xl overflow-hidden bg-surface-base shadow-card">
        <button
          onClick={() => setShowCode(!showCode)}
          className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-050 transition-colors cursor-pointer"
        >
          <div className="flex items-center gap-2 text-[12px] font-semibold text-slate-600">
            {showCode ? <ChevronDown className="w-3.5 h-3.5 text-slate-400" /> : <ChevronRight className="w-3.5 h-3.5 text-slate-400" />}
            View Python script
          </div>
          <span className="font-mono text-[10px] bg-slate-900 text-slate-300 px-2 py-0.5 rounded border border-slate-700 font-bold tracking-wider">
            .py
          </span>
        </button>
        {showCode && (
          <div className="border-t border-slate-200 overflow-x-auto">
            <SyntaxHighlighter
              language="python"
              style={oneDark}
              customStyle={{
                background: '#1a1f2e',
                padding: '16px',
                margin: 0,
                fontSize: '12px',
                lineHeight: '1.6',
                fontFamily: "'Source Code Pro', monospace",
                borderRadius: 0,
              }}
            >
              {script || "# No code executed."}
            </SyntaxHighlighter>
          </div>
        )}
      </div>

      {/* ── 7. Follow-up Bar ── */}
      <div className="sticky bottom-0 -mx-6 px-6 pb-4 pt-4 bg-gradient-to-t from-surface-subtle via-surface-subtle/95 to-transparent z-30">
        <form onSubmit={handleRunFollowUp}>
          <div className="flex items-center bg-surface-base border border-slate-200 rounded-xl px-3 py-2.5 shadow-card-md focus-within:border-crimson-400/70 focus-within:shadow-[0_0_0_3px_rgba(200,29,37,0.08),0_4px_12px_rgba(0,0,0,0.08)] transition-all">
            <input
              type="text"
              value={followUpText}
              onChange={e => setFollowUpText(e.target.value)}
              placeholder="Follow up — e.g. 'Show this by quarter' or 'Filter to Islamic banks only'"
              className="flex-1 bg-transparent border-none outline-none px-2 py-1 text-[13px] text-slate-900 placeholder:text-slate-400 focus:ring-0"
            />
            <button
              type="submit"
              disabled={!followUpText.trim()}
              className="flex items-center gap-1.5 bg-crimson-600 hover:bg-crimson-700 disabled:opacity-40 disabled:bg-slate-200 disabled:text-slate-400 text-white px-4 py-2 rounded-lg text-[12px] font-bold transition-all cursor-pointer shrink-0 ml-2 shadow-sm active:scale-[0.97]"
            >
              <Send className="w-3 h-3" />
              Run
            </button>
          </div>
        </form>
      </div>

    </div>
  )
}
