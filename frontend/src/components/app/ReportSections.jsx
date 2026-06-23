import { useState, useMemo } from "react"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../ui/table"
import { ChevronRight, ChevronDown, ChevronUp, Play, ChevronsUpDown, Download, ListTodo, CheckCircle2, DollarSign, Activity, Coins } from "lucide-react"
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism"

export default function ReportSections({ result, query, script, plan = [], taskId, onFollowUp }) {
  const [showCode, setShowCode] = useState(false)
  const [followUpText, setFollowUpText] = useState("")
  const [sortCol, setSortCol] = useState(null)
  const [sortDir, setSortDir] = useState("desc")

  // Parse result robustly
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
    } catch (e) {
      console.warn("Could not parse result string to JSON:", e)
      return null
    }
  }, [result])

  const summary = parsed?.summary || (typeof result === "string" ? result : "Analysis complete.")
  const columns = parsed?.columns || []
  const rows = parsed?.rows || []
  const rawText = parsed?.raw || ""

  const hasTableData = columns.length > 0 && rows.length > 0

  // Calculate estimated tokens & API costs dynamically
  const stats = useMemo(() => {
    const rounds = plan.length || 1
    // Standard Gemini billing estimates
    const estInputTokens = rounds * 2500
    const estOutputTokens = rounds * 400
    const estCost = (estInputTokens * 0.00000125) + (estOutputTokens * 0.000005)
    return {
      rounds,
      tokens: estInputTokens + estOutputTokens,
      cost: estCost
    }
  }, [plan])

  // Identify numeric columns
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
        if (isNaN(num)) {
          isNumeric = false
          break
        }
      }
      map[colIdx] = isNumeric && checks > 0
    }
    return map
  }, [columns, rows, hasTableData])

  // Identify entity and metric columns for Highlights
  const highlights = useMemo(() => {
    if (!hasTableData) {
      return [
        { label: "Highest Risk", val: "None", sub: "No data available", topBorder: "border-t-[#DC2626]", textClass: "text-[#DC2626]" },
        { label: "Watch", val: "None", sub: "No data available", topBorder: "border-t-amber-600", textClass: "text-amber-600" },
        { label: "Lowest Exposure", val: "None", sub: "No data available", topBorder: "border-t-slate-400", textClass: "text-slate-400" },
      ]
    }

    // Entity column
    let entityIdx = 0
    for (let i = 0; i < columns.length; i++) {
      const col = columns[i].toLowerCase()
      if (col.includes("bank") || col.includes("lfi") || col.includes("name") || col.includes("institution") || col.includes("house") || col.includes("exchange") || col.includes("entity")) {
        entityIdx = i
        break
      }
    }

    // Metric column
    let metricIdx = -1
    for (let i = 0; i < columns.length; i++) {
      if (i === entityIdx) continue
      const col = columns[i].toLowerCase()
      if (col.includes("score") || col.includes("risk") || col.includes("ratio") || col.includes("amount") || col.includes("volume") || col.includes("count") || col.includes("sum") || col.includes("txs") || col.includes("val")) {
        metricIdx = i
        break
      }
    }
    if (metricIdx === -1) {
      for (let i = 0; i < columns.length; i++) {
        if (i === entityIdx) continue
        if (numericColumnMap[i]) {
          metricIdx = i
          break
        }
      }
    }

    // Sort descending by metric
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
      if (metricIdx !== -1) {
        return `${columns[metricIdx]}: ${row[metricIdx]}`
      }
      return columns[1] ? `${columns[1]}: ${row[1]}` : "Matched LFI"
    }

    return [
      { 
        label: "Highest Risk", 
        val: highRow[entityIdx] || "N/A", 
        sub: getSubtext(highRow), 
        topBorder: "border-t-[#DC2626]", 
        textClass: "text-[#DC2626]" 
      },
      { 
        label: "Watch", 
        val: watchRow[entityIdx] || "N/A", 
        sub: getSubtext(watchRow), 
        topBorder: "border-t-amber-600", 
        textClass: "text-amber-600" 
      },
      { 
        label: "Lowest Exposure", 
        val: lowRow[entityIdx] || "N/A", 
        sub: getSubtext(lowRow), 
        topBorder: "border-t-slate-400", 
        textClass: "text-slate-400" 
      },
    ]
  }, [columns, rows, hasTableData, numericColumnMap])

  // Sorting
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
        const valA = a[sortCol]
        const valB = b[sortCol]
        const numA = parseFloat(String(valA).replace(/[^0-9.-]/g, ""))
        const numB = parseFloat(String(valB).replace(/[^0-9.-]/g, ""))
        
        if (!isNaN(numA) && !isNaN(numB)) {
          return sortDir === "asc" ? numA - numB : numB - numA
        }
        return sortDir === "asc" 
          ? String(valA).localeCompare(String(valB)) 
          : String(valB).localeCompare(String(valA))
      })
    }
    return list
  }, [rows, sortCol, sortDir, hasTableData])

  // Identify risk column index
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
        <span className="px-2 py-0.5 rounded-[2px] text-[9px] font-bold tracking-wide uppercase bg-red-100 text-red-600 border border-red-200">
          High
        </span>
      )
    }
    if (norm.includes("medium") || norm.includes("med") || norm.includes("warning") || norm.includes("watch")) {
      return (
        <span className="px-2 py-0.5 rounded-[2px] text-[9px] font-bold tracking-wide uppercase bg-amber-100 text-amber-600 border border-amber-300">
          Medium
        </span>
      )
    }
    if (norm.includes("low") || norm.includes("safe") || norm.includes("info")) {
      return (
        <span className="px-2 py-0.5 rounded-[2px] text-[9px] font-bold tracking-wide uppercase bg-green-100 text-green-600 border border-green-200">
          Low
        </span>
      )
    }
    return val
  }

  // CSV Exporter
  const handleExportCSV = () => {
    if (!hasTableData) return
    const csvRows = []
    
    // Header
    csvRows.push(columns.map(col => `"${String(col).replace(/"/g, '""')}"`).join(','))
    
    // Body
    rows.forEach(row => {
      csvRows.push(row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    })
    
    const csvString = csvRows.join('\n')
    const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' })
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
    <div className="flex flex-col gap-6 pb-24 font-sans w-full">
      
      {/* 1. Summary Card */}
      <div className="bg-surface-base border border-slate-200 border-l-2 border-l-crimson-600 rounded-[4px] p-5 shadow-sm">
        <h3 className="text-[9px] font-bold uppercase tracking-widest text-crimson-600 mb-1">
          Summary
        </h3>
        <p className="text-[13px] text-slate-600 leading-[1.65] font-sans">
          {summary}
        </p>
      </div>

      {/* 2. Observability Metrics Banner */}
      <div className="grid grid-cols-3 gap-4 border border-slate-100 bg-slate-050 rounded-xl p-4 shadow-sm select-none">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 shrink-0">
            <Activity className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wider">Analysis Steps</div>
            <div className="font-mono text-xs font-semibold text-slate-900">{stats.rounds} iterations</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 shrink-0">
            <Coins className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wider">Estimated Tokens</div>
            <div className="font-mono text-xs font-semibold text-slate-900">{stats.tokens.toLocaleString()} total</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 shrink-0">
            <DollarSign className="w-4 h-4 text-green-600" />
          </div>
          <div>
            <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wider">Model Cost</div>
            <div className="font-mono text-xs font-semibold text-slate-900">${stats.cost.toFixed(5)}</div>
          </div>
        </div>
      </div>

      {hasTableData && (
        <>
          {/* 3. Metric Callouts Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {highlights.map((c, idx) => (
              <div 
                key={idx}
                className={`p-4 rounded-[4px] border border-slate-100 bg-surface-base border-t-[3px] ${c.topBorder} shadow-sm`}
              >
                <div className={`text-[9px] font-bold uppercase tracking-wider mb-1 ${c.textClass}`}>
                  {c.label}
                </div>
                <div className="text-[15px] font-semibold text-slate-900 tracking-tight mb-0.5 truncate">
                  {c.val}
                </div>
                <div className="text-[10px] text-slate-400 font-sans">
                  {c.sub}
                </div>
              </div>
            ))}
          </div>

          {/* 4. Plan Step Progress Checklist */}
          {plan && plan.length > 0 && (
            <div className="bg-surface-base border border-slate-100 rounded-xl p-5 shadow-sm">
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-3.5 flex items-center gap-1.5">
                <ListTodo className="w-4 h-4 text-crimson-600" />
                Supervisory Plan Workflow
              </h3>
              <div className="flex flex-col gap-2.5">
                {plan.map((step, idx) => (
                  <div key={idx} className="flex items-start gap-2.5 text-[12px] text-slate-600 leading-normal font-sans">
                    <CheckCircle2 className="w-4 h-4 text-green-600 shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <span className="font-semibold text-slate-800 mr-1">Step {idx + 1}:</span>
                      {step}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 5. Sortable Data Table */}
          <div className="bg-surface-base border border-slate-100 rounded-xl overflow-hidden shadow-sm">
            {/* Table Header Bar */}
            <div className="flex items-center justify-between px-4 py-2.5 bg-surface-muted border-b border-slate-100 text-[10px] text-slate-400">
              <div className="font-mono">{rows.length} rows</div>
              <div className="flex items-center gap-3">
                <button 
                  onClick={handleExportCSV}
                  className="flex items-center gap-1 text-slate-500 hover:text-slate-900 transition-colors cursor-pointer font-semibold font-sans"
                >
                  <Download className="w-3.5 h-3.5" />
                  Export CSV
                </button>
                <span>|</span>
                <div className="text-[9px]">Click columns to sort</div>
              </div>
            </div>

            <Table>
              <TableHeader className="bg-transparent border-b border-slate-100">
                <TableRow className="hover:bg-transparent">
                  {/* Rank header */}
                  <TableHead className="text-[9px] font-bold text-slate-400 uppercase tracking-wider w-8 h-10 px-4">
                    #
                  </TableHead>
                  
                  {columns.map((col, idx) => {
                    const isSorted = sortCol === idx
                    const isNumeric = numericColumnMap[idx]
                    return (
                      <TableHead 
                        key={idx} 
                        onClick={() => handleSort(idx)}
                        className={`text-[9px] font-bold text-slate-400 uppercase tracking-wider h-10 px-4 cursor-pointer hover:text-slate-900 transition-colors select-none ${
                          isNumeric ? "text-right" : "text-left"
                        }`}
                      >
                        <div className={`flex items-center gap-1 ${isNumeric ? "justify-end" : "justify-start"}`}>
                          <span>{col}</span>
                          {isSorted ? (
                            sortDir === "asc" ? <ChevronUp className="w-3 h-3 text-slate-900" /> : <ChevronDown className="w-3 h-3 text-slate-900" />
                          ) : (
                            <ChevronsUpDown className="w-3 h-3 text-slate-300 opacity-50" />
                          )}
                        </div>
                      </TableHead>
                    )
                  })}
                </TableRow>
              </TableHeader>
              <TableBody className="divide-y divide-slate-50">
                {sortedDisplayRows.map((row, i) => (
                  <TableRow key={i} className="hover:bg-surface-muted transition-colors">
                    {/* Rank cell in Source Code Pro */}
                    <TableCell className="font-mono text-slate-400 text-xs px-4 py-3 w-8">
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
                          <TableCell key={colIdx} className="font-semibold text-slate-900 text-[13px] px-4 py-3 font-sans">
                            {cell}
                          </TableCell>
                        )
                      }

                      return (
                        <TableCell 
                          key={colIdx} 
                          className={`text-[13px] px-4 py-3 ${
                            isNumeric 
                              ? "font-mono text-right text-slate-900" 
                              : "text-slate-600 font-sans"
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
        </>
      )}

      {/* Fallback raw display card if no table data and raw text exists */}
      {!hasTableData && rawText && (
        <div className="bg-surface-base border border-slate-100 rounded-[4px] p-5 shadow-sm font-mono text-xs text-slate-600 leading-relaxed overflow-x-auto">
          {rawText}
        </div>
      )}

      {/* 4. Expandable Python Code Drawer */}
      <div className="flex flex-col border border-slate-100 rounded-[4px] overflow-hidden bg-surface-base shadow-sm">
        <div className="bg-surface-base border-t border-slate-100 p-2 flex items-center justify-between select-none">
          <button 
            onClick={() => setShowCode(!showCode)}
            className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-slate-600 transition-colors cursor-pointer font-sans"
          >
            {showCode ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            View Python script
          </button>
          <span className="font-mono text-[9px] bg-slate-050 text-slate-400 px-1.5 py-0.5 rounded border border-slate-100 font-bold uppercase tracking-wider">
            py
          </span>
        </div>

        {showCode && (
          <div className="border-t border-slate-100 bg-surface-base p-4 overflow-x-auto">
            <SyntaxHighlighter 
              language="python" 
              style={oneLight}
              customStyle={{ 
                background: 'transparent', 
                padding: 0, 
                margin: 0, 
                fontSize: '11px',
                lineHeight: '1.5',
                fontFamily: "'Source Code Pro', monospace"
              }}
            >
              {script || "# No code executed."}
            </SyntaxHighlighter>
          </div>
        )}
      </div>

      {/* 5. Follow-up Prompt Bar */}
      <div className="sticky bottom-0 bg-surface-base border-t border-slate-100 p-2.5 z-30">
        <form onSubmit={handleRunFollowUp} className="w-full">
          <div className="flex items-center bg-surface-subtle border border-slate-200 rounded-lg p-[7px] focus-within:border-crimson-600/50 transition-colors">
            <input 
              type="text"
              value={followUpText}
              onChange={e => setFollowUpText(e.target.value)}
              placeholder="Follow up — e.g. 'Show this by quarter' or 'Filter to Islamic banks only'"
              className="flex-1 bg-transparent border-none outline-none px-2 text-[13px] text-slate-900 placeholder:text-slate-400 focus:ring-0 focus:border-none"
            />
            <button
              type="submit"
              disabled={!followUpText.trim()}
              className="bg-crimson-600 hover:bg-crimson-500 disabled:opacity-50 disabled:bg-slate-200 disabled:text-slate-400 text-white px-4 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shrink-0 ml-2"
            >
              <Play className="w-3 h-3 fill-current stroke-none" />
              Run
            </button>
          </div>
        </form>
      </div>

    </div>
  )
}