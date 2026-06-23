import { useState, useMemo } from "react"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../ui/table"
import {
  ChevronRight, ChevronDown, ChevronUp, Play, ChevronsUpDown,
  Download, ListTodo, CheckCircle2, DollarSign, Activity, Coins,
  TrendingUp, AlertTriangle, TrendingDown, Send
} from "lucide-react"
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism"

export default function ReportSections({ result, query, script, plan = [], taskId, onFollowUp }) {
  const [showCode, setShowCode] = useState(false)
  const [followUpText, setFollowUpText] = useState("")
  const [sortCol, setSortCol] = useState(null)
  const [sortDir, setSortDir] = useState("desc")

  const parsed = useMemo(() => {
    if (!result) return null
    try {
      let cleanResult = typeof result === "string" ? result.trim() : JSON.stringify(result)
      if (cleanResult.startsWith("```json")) {
        cleanResult = cleanResult.replace(/^```json/, "").replace(/```$/, "")
      } else if (cleanResult.startsWith("```")) {
        cleanResult = cleanResult.replace(/^```/, "").replace(/```$/, "")
      }
      return JSON.parse(cleanResult.trim())
    } catch {
      return null
    }
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
      let isNumeric = true
      let checks = 0
      for (let r = 0; r < Math.min(rows.length, 10); r++) {
        const cell = rows[r][colIdx]
        if (cell === undefined || cell === null || cell === "") continue
        checks++
        const num = parseFloat(String(cell).replace(/[^0-9.-]/g, ""))
        if (isNaN(num)) { isNumeric = false; break }
      }
      map[colIdx] = isNumeric && checks > 0
    }
    return map
  }, [columns, rows, hasTableData])

  const highlights = useMemo(() => {
    const noData = [
      { label: "Highest Risk", val: "None", sub: "No data available", accentColor: "#DC2626", bg: "bg-red-050", border: "border-red-100", icon: AlertTriangle, iconColor: "text-red-500" },
      { label: "Watch", val: "None", sub: "No data available", accentColor: "#D97706", bg: "bg-amber-50", border: "border-amber-100", icon: TrendingUp, iconColor: "text-amber-500" },
      { label: "Lowest Exposure", val: "None", sub: "No data available", accentColor: "#8890A4", bg: "bg-slate-050", border: "border-slate-100", icon: TrendingDown, iconColor: "text-slate-400" },
    ]
    if (!hasTableData) return noData

    let entityIdx = 0
    for (let i = 0; i < columns.length; i++) {
      const col = columns[i].toLowerCase()
      if (col.includes("bank") || col.includes("lfi") || col.includes("name") || col.includes("institution") || col.includes("house") || col.includes("exchange") || col.includes("entity")) {
        entityIdx = i; break
      }
    }

    let metricIdx = -1
    for (let i = 0; i < columns.length; i++) {
      if (i === entityIdx) continue
      const col = columns[i].toLowerCase()
      if (col.includes("score") || col.includes("risk") || col.includes("ratio") || col.includes("amount") || col.includes("volume") || col.includes("count") || col.includes("sum") || col.includes("txs") || col.includes("val")) {
        metricIdx = i; break
      }
    }
    if (metricIdx === -1) {
      for (let i = 0; i < columns.length; i++) {
        if (i === entityIdx) continue
        if (numericColumnMap[i]) { metricIdx = i; break }
      }
    }

    let sorted = [...rows]
    if (metricIdx !== -1) {
      sorted.sort((a, b) => {
        const valA = parseFloat(String(a[metricIdx]).replace(/[^0-9.-]/g, "")) || 0
        const valB = parseFloat(String(b[metricIdx]).replace(/[^0-9.-]/g, "")) || 0
        return valB - valA
      })
    }

    const highRow = sorted[0]
    const watchRow = sorted[Math.min(1, sorted.length - 1)] || sorted[0]
    const lowRow = sorted[sorted.length - 1]

    const getSubtext = (row) => {
      if (metricIdx !== -1) return `${columns[metricIdx]}: ${row[metricIdx]}`
      return columns[1] ? `${columns[1]}: ${row[1]}` : "Matched LFI"
    }

    return [
      { label: "Highest Risk", val: highRow[entityIdx] || "N/A", sub: getSubtext(highRow), accentColor: "#DC2626", bg: "bg-red-050", border: "border-red-100", icon: AlertTriangle, iconColor: "text-red-500" },
      { label: "Watch", val: watchRow[entityIdx] || "N/A", sub: getSubtext(watchRow), accentColor: "#D97706", bg: "bg-amber-50", border: "border-amber-100", icon: TrendingUp, iconColor: "text-amber-500" },
      { label: "Lowest Exposure", val: lowRow[entityIdx] || "N/A", sub: getSubtext(lowRow), accentColor: "#8890A4", bg: "bg-slate-050", border: "border-slate-200", icon: TrendingDown, iconColor: "text-slate-400" },
    ]
  }, [columns, rows, hasTableData, numericColumnMap])

  const handleSort = (colIdx) => {
    if (sortCol === colIdx) {
      setSortDir(sortDir === "asc" ? "desc" : "asc")
    } else {
      setSortCol(colIdx)
      setSortDir("desc")
    }
  }

  const sortedDisplayRows = useMemo(() => {
    if (!hasTableData) return []
    let list = [...rows]
    if (sortCol !== null) {
      list.sort((a, b) => {
        const valA = a[sortCol], valB = b[sortCol]
        const numA = parseFloat(String(valA).replace(/[^0-9.-]/g, ""))
        const numB = parseFloat(String(valB).replace(/[^0-9.-]/g, ""))
        if (!isNaN(numA) && !isNaN(numB)) return sortDir === "asc" ? numA - numB : numB - numA
        return sortDir === "asc"
          ? String(valA).localeCompare(String(valB))
          : String(valB).localeCompare(String(valA))
      })
    }
    return list
  }, [rows, sortCol, sortDir, hasTableData])

  const riskColIdx = useMemo(() => {
    return columns.findIndex(col => {
      const c = col.toLowerCase()
      return c.includes("risk") || c.includes("level") || c.includes("alert") || c.includes("class")
    })
  }, [columns])

  const renderCellBadge = (val) => {
    const norm = String(val).trim().toLowerCase()
    if (norm.includes("high") || norm.includes("danger") || norm.includes("critical")) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold tracking-wide uppercase bg-red-100 text-red-600 border border-red-200">
          High
        </span>
      )
    }
    if (norm.includes("medium") || norm.includes("med") || norm.includes("warning") || norm.includes("watch")) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold tracking-wide uppercase bg-amber-100 text-amber-700 border border-amber-200">
          Medium
        </span>
      )
    }
    if (norm.includes("low") || norm.includes("safe") || norm.includes("info")) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold tracking-wide uppercase bg-green-100 text-green-700 border border-green-200">
          Low
        </span>
      )
    }
    return val
  }

  const handleExportCSV = () => {
    if (!hasTableData) return
    const csvRows = []
    csvRows.push(columns.map(col => `"${String(col).replace(/"/g, '""')}"`).join(','))
    rows.forEach(row => {
      csvRows.push(row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    })
    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.setAttribute('href', url)
    link.setAttribute('download', `ds_star_export_${Date.now()}.csv`)
    link.style.visibility = 'hidden'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const handleRunFollowUp = (e) => {
    e.preventDefault()
    if (!followUpText.trim()) return
    onFollowUp(followUpText)
    setFollowUpText("")
  }

  return (
    <div className="flex flex-col gap-5 pb-28 font-sans w-full">

      {/* 1. Summary Card */}
      <div className="relative bg-surface-base border border-slate-100 rounded-xl p-5 shadow-card overflow-hidden">
        {/* Left accent bar */}
        <div className="absolute left-0 top-0 bottom-0 w-1 rounded-l-xl bg-gradient-to-b from-crimson-600 to-crimson-400" />
        <div className="pl-3">
          <div className="flex items-center gap-1.5 mb-2">
            <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-crimson-600">
              Summary
            </span>
          </div>
          <p className="text-[14px] text-slate-700 leading-[1.7]">
            {summary}
          </p>
        </div>
      </div>

      {/* 2. Observability Metrics */}
      <div className="grid grid-cols-3 gap-3">
        {[
          {
            icon: Activity, iconBg: "bg-blue-050", iconColor: "text-blue-600",
            label: "Analysis Steps", value: `${stats.rounds} iteration${stats.rounds !== 1 ? 's' : ''}`, mono: true
          },
          {
            icon: Coins, iconBg: "bg-amber-50", iconColor: "text-amber-600",
            label: "Estimated Tokens", value: `${stats.tokens.toLocaleString()}`, mono: true
          },
          {
            icon: DollarSign, iconBg: "bg-green-050", iconColor: "text-green-700",
            label: "Model Cost", value: `$${stats.cost.toFixed(5)}`, mono: true
          },
        ].map(({ icon: Icon, iconBg, iconColor, label, value, mono }) => (
          <div key={label} className="bg-surface-base border border-slate-100 rounded-xl p-4 shadow-card flex items-center gap-3">
            <div className={`w-9 h-9 rounded-lg ${iconBg} flex items-center justify-center shrink-0`}>
              <Icon className={`w-4.5 h-4.5 ${iconColor}`} />
            </div>
            <div>
              <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">{label}</div>
              <div className={`text-[13px] font-semibold text-slate-900 ${mono ? 'font-mono' : ''}`}>{value}</div>
            </div>
          </div>
        ))}
      </div>

      {hasTableData && (
        <>
          {/* 3. Highlight Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {highlights.map((c, idx) => {
              const Icon = c.icon
              return (
                <div
                  key={idx}
                  className={`relative bg-surface-base border ${c.border} rounded-xl p-4 shadow-card overflow-hidden`}
                >
                  <div className="absolute top-0 left-0 right-0 h-1 rounded-t-xl" style={{ background: c.accentColor }} />
                  <div className="flex items-start justify-between mb-2 pt-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: c.accentColor }}>
                      {c.label}
                    </span>
                    <div className={`w-7 h-7 rounded-lg ${c.bg} flex items-center justify-center`}>
                      <Icon className={`w-3.5 h-3.5 ${c.iconColor}`} />
                    </div>
                  </div>
                  <div className="text-[16px] font-bold text-slate-900 tracking-tight truncate mb-0.5">
                    {c.val}
                  </div>
                  <div className="text-[11px] text-slate-400 font-medium truncate">
                    {c.sub}
                  </div>
                </div>
              )
            })}
          </div>

          {/* 4. Supervisory Plan */}
          {plan && plan.length > 0 && (
            <div className="bg-surface-base border border-slate-100 rounded-xl p-5 shadow-card">
              <h3 className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.15em] text-slate-500 mb-4">
                <ListTodo className="w-3.5 h-3.5 text-crimson-600" />
                Supervisory Plan Workflow
              </h3>
              <div className="flex flex-col gap-3">
                {plan.map((step, idx) => (
                  <div key={idx} className="flex items-start gap-3">
                    <div className="w-5 h-5 rounded-full bg-green-050 border border-green-200 flex items-center justify-center shrink-0 mt-0.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-green-600" />
                    </div>
                    <div className="flex-1 text-[13px] text-slate-600 leading-snug">
                      <span className="font-semibold text-slate-800 mr-1">Step {idx + 1}:</span>
                      {step}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 5. Data Table */}
          <div className="bg-surface-base border border-slate-100 rounded-xl overflow-hidden shadow-card">
            {/* Table toolbar */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 bg-slate-050/60">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[11px] font-semibold text-slate-500 bg-surface-base border border-slate-200 px-2 py-0.5 rounded-md">
                  {rows.length} rows
                </span>
                <span className="text-[10px] text-slate-400">· Click column headers to sort</span>
              </div>
              <button
                onClick={handleExportCSV}
                className="flex items-center gap-1.5 text-[12px] font-semibold text-slate-500 hover:text-slate-900 px-3 py-1.5 rounded-lg hover:bg-surface-base border border-transparent hover:border-slate-200 transition-all cursor-pointer"
              >
                <Download className="w-3.5 h-3.5" />
                Export CSV
              </button>
            </div>

            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent border-b border-slate-100">
                    <TableHead className="text-[10px] font-bold text-slate-400 uppercase tracking-wider w-10 h-11 px-4 bg-slate-050/30">
                      #
                    </TableHead>
                    {columns.map((col, idx) => {
                      const isSorted = sortCol === idx
                      const isNumeric = numericColumnMap[idx]
                      return (
                        <TableHead
                          key={idx}
                          onClick={() => handleSort(idx)}
                          className={`text-[10px] font-bold text-slate-400 uppercase tracking-wider h-11 px-4 cursor-pointer hover:text-slate-800 hover:bg-slate-050 transition-colors select-none bg-slate-050/30 ${
                            isNumeric ? "text-right" : "text-left"
                          } ${isSorted ? "text-slate-800 bg-slate-050" : ""}`}
                        >
                          <div className={`flex items-center gap-1 ${isNumeric ? "justify-end" : "justify-start"}`}>
                            <span>{col}</span>
                            {isSorted ? (
                              sortDir === "asc"
                                ? <ChevronUp className="w-3 h-3" />
                                : <ChevronDown className="w-3 h-3" />
                            ) : (
                              <ChevronsUpDown className="w-3 h-3 opacity-30" />
                            )}
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
                      className={`hover:bg-surface-subtle transition-colors border-b border-slate-050 ${
                        i % 2 === 0 ? "" : "bg-slate-050/30"
                      }`}
                    >
                      <TableCell className="font-mono text-[11px] text-slate-400 px-4 py-3 w-10 font-bold">
                        {i + 1}
                      </TableCell>
                      {row.map((cell, colIdx) => {
                        const isNumeric = numericColumnMap[colIdx]
                        const isRisk = colIdx === riskColIdx

                        if (isRisk) {
                          return (
                            <TableCell key={colIdx} className="px-4 py-3">
                              {renderCellBadge(cell)}
                            </TableCell>
                          )
                        }

                        if (colIdx === 0) {
                          return (
                            <TableCell key={colIdx} className="font-semibold text-slate-900 text-[13px] px-4 py-3">
                              {cell}
                            </TableCell>
                          )
                        }

                        return (
                          <TableCell
                            key={colIdx}
                            className={`text-[13px] px-4 py-3 ${
                              isNumeric
                                ? "font-mono text-right text-slate-800 font-semibold"
                                : "text-slate-600"
                            }`}
                          >
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

      {/* Raw text fallback */}
      {!hasTableData && rawText && (
        <div className="bg-surface-base border border-slate-100 rounded-xl p-5 shadow-card font-mono text-[12px] text-slate-600 leading-relaxed overflow-x-auto">
          {rawText}
        </div>
      )}

      {/* 6. Python Script Viewer */}
      <div className="border border-slate-100 rounded-xl overflow-hidden bg-surface-base shadow-card">
        <button
          onClick={() => setShowCode(!showCode)}
          className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-050 transition-colors cursor-pointer"
        >
          <div className="flex items-center gap-2 text-[12px] font-semibold text-slate-600">
            {showCode
              ? <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
              : <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
            }
            View Python script
          </div>
          <span className="font-mono text-[10px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded-md border border-slate-200 font-bold uppercase tracking-wider">
            .py
          </span>
        </button>

        {showCode && (
          <div className="border-t border-slate-100 bg-slate-050/50 p-4 overflow-x-auto">
            <SyntaxHighlighter
              language="python"
              style={oneLight}
              customStyle={{
                background: 'transparent',
                padding: 0,
                margin: 0,
                fontSize: '12px',
                lineHeight: '1.6',
                fontFamily: "'Source Code Pro', monospace"
              }}
            >
              {script || "# No code executed."}
            </SyntaxHighlighter>
          </div>
        )}
      </div>

      {/* 7. Follow-up Prompt Bar */}
      <div className="sticky bottom-0 -mx-6 px-6 pb-4 pt-3 bg-gradient-to-t from-surface-subtle via-surface-subtle/95 to-transparent z-30">
        <form onSubmit={handleRunFollowUp}>
          <div className="flex items-center bg-surface-base border border-slate-200 rounded-xl px-3 py-2 shadow-card-md focus-within:border-crimson-400/60 focus-within:shadow-[0_0_0_3px_rgba(200,29,37,0.08)] transition-all">
            <input
              type="text"
              value={followUpText}
              onChange={e => setFollowUpText(e.target.value)}
              placeholder="Follow up — e.g. 'Show this by quarter' or 'Filter to Islamic banks only'"
              className="flex-1 bg-transparent border-none outline-none px-2 py-1.5 text-[13px] text-slate-900 placeholder:text-slate-400 focus:ring-0"
            />
            <button
              type="submit"
              disabled={!followUpText.trim()}
              className="flex items-center gap-1.5 bg-crimson-600 hover:bg-crimson-700 disabled:opacity-40 disabled:bg-slate-200 disabled:text-slate-400 text-white px-4 py-1.5 rounded-lg text-[12px] font-semibold transition-all cursor-pointer shrink-0 ml-2 shadow-sm active:scale-[0.97]"
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
