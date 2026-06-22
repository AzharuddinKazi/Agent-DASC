import { useState, useMemo } from "react"
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism' // A clean, VSCode-like dark theme

export default function ReportSections({ result, query, script }) {
  const [activeTab, setActiveTab] = useState("table")

  // Safely parse the JSON and normalize it into headers and rows arrays
  const { parsedData, isJson, headers, tableRows, summary, rawText } = useMemo(() => {
    if (!result) return { parsedData: null, isJson: false, headers: [], tableRows: [], summary: null, rawText: null }

    try {
      let cleanResult = result
      if (typeof result === "string") {
        cleanResult = result.replace(/```json\n?/g, "").replace(/```/g, "").trim()
      }
      
      const parsed = typeof cleanResult === "string" ? JSON.parse(cleanResult) : cleanResult
      
      let extractedHeaders = []
      let extractedRows = []
      let extractedSummary = parsed?.summary || null
      let extractedRaw = parsed?.raw || null

      // Check if it's the new "Split" format (columns and rows arrays)
      if (parsed && Array.isArray(parsed.columns) && Array.isArray(parsed.rows)) {
        extractedHeaders = parsed.columns
        extractedRows = parsed.rows
      } 
      // Fallback: Check if it's an array of objects (Records format)
      else if (Array.isArray(parsed) && parsed.length > 0 && typeof parsed[0] === "object") {
        extractedHeaders = Object.keys(parsed[0])
        extractedRows = parsed.map(row => extractedHeaders.map(h => row[h]))
      }

      return { 
        parsedData: parsed, 
        isJson: true, 
        headers: extractedHeaders, 
        tableRows: extractedRows,
        summary: extractedSummary,
        rawText: extractedRaw
      }
    } catch (e) {
      return { parsedData: result, isJson: false, headers: [], tableRows: [], summary: null, rawText: null }
    }
  }, [result])

  return (
    <div className="flex flex-col gap-6 h-full">
      {/* Query & Summary Header */}
      <div className="flex flex-col gap-2">
        <h2 className="text-sm font-medium text-zinc-100">{query}</h2>
        {summary && (
          <p className="text-xs text-zinc-400 leading-relaxed border-l-2 border-violet-500/50 pl-3">
            {summary}
          </p>
        )}
      </div>

      {/* 3-View Card Layout */}
      <div className="flex flex-col flex-1 rounded-xl border border-zinc-800/60 bg-zinc-900/30 overflow-hidden shadow-sm">
        
        {/* Navigation Tabs */}
        <div className="flex items-center gap-1 border-b border-zinc-800/60 p-2 bg-zinc-950/50">
          <TabButton active={activeTab === "table"} onClick={() => setActiveTab("table")} icon="ti-table">
            Data Table
          </TabButton>
          <TabButton active={activeTab === "code"} onClick={() => setActiveTab("code")} icon="ti-code">
            Python Script
          </TabButton>
          <TabButton active={activeTab === "raw"} onClick={() => setActiveTab("raw")} icon="ti-braces">
            Raw Output
          </TabButton>
        </div>

        {/* Tab Content Window */}
        <div className="flex-1 overflow-auto bg-[#0a0a0a]">
          
          {/* View 1: Data Table */}
          {activeTab === "table" && (
            <div className="min-w-full inline-block align-middle">
              {isJson && headers.length > 0 ? (
                <table className="min-w-full text-left text-xs text-zinc-400 border-collapse">
                  <thead className="bg-zinc-900/80 sticky top-0 backdrop-blur-md text-zinc-300 border-b border-zinc-800/60 z-10">
                    <tr>
                      {headers.map((h) => (
                        <th key={h} className="px-5 py-3 font-medium whitespace-nowrap capitalize tracking-wide">
                          {h.replace(/_/g, " ")}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/40">
                    {tableRows.map((row, rowIndex) => (
                      <tr key={rowIndex} className="hover:bg-zinc-800/20 transition-colors">
                        {row.map((cell, cellIndex) => (
                          <td key={`${rowIndex}-${cellIndex}`} className="px-5 py-3 whitespace-nowrap">
                            {cell !== null && typeof cell === "object" 
                              ? JSON.stringify(cell) 
                              : String(cell ?? "—")}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="p-6 text-zinc-400 text-xs whitespace-pre-wrap font-mono leading-relaxed">
                  {typeof parsedData === "string" ? parsedData : JSON.stringify(parsedData, null, 2)}
                </div>
              )}
            </div>
          )}

{/* View 2: Python Code */}
          {activeTab === "code" && (
            <div className="p-5 overflow-auto max-h-full">
              <SyntaxHighlighter 
                language="python" 
                style={vscDarkPlus}
                customStyle={{
                  backgroundColor: 'transparent', // Forces it to blend with your zinc-900 background
                  padding: 0,
                  margin: 0,
                  fontSize: '0.75rem', // matches text-xs
                  lineHeight: '1.625', // matches leading-relaxed
                }}
                codeTagProps={{
                  className: "font-mono"
                }}
              >
                {script || "# No script recorded for this task."}
              </SyntaxHighlighter>
            </div>
          )}

          {/* View 3: Raw JSON / Terminal */}
          {activeTab === "raw" && (
            <div className="p-5">
              <pre className="text-[11px] text-zinc-500 font-mono leading-relaxed whitespace-pre-wrap">
                <code>
                  {rawText ? rawText : (isJson ? JSON.stringify(parsedData, null, 2) : String(result))}
                </code>
              </pre>
            </div>
          )}
          
        </div>
      </div>
    </div>
  )
}

function TabButton({ active, onClick, icon, children }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${
        active ? "bg-zinc-800/80 text-zinc-100 shadow-sm" : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/40"
      }`}
    >
      <i className={`ti ${icon} text-sm`} />
      {children}
    </button>
  )
}