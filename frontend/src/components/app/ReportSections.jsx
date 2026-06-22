import { useState } from "react"

function parseTable(text) {
  if (!text) return null
  const lines = text.trim().split("\n").filter(l => l.trim())
  if (lines.length < 2) return null
  
  // detect column positions from header line
  const header = lines[0]
  const colPositions = []
  let inWord = false
  for (let i = 0; i < header.length; i++) {
    if (header[i] !== ' ' && !inWord) { colPositions.push(i); inWord = true }
    else if (header[i] === ' ') inWord = false
  }
  if (colPositions.length < 2) return null

  const rows = lines.map(line => {
    return colPositions.map((start, i) => {
      const end = colPositions[i + 1] ?? line.length
      return line.slice(start, end).trim()
    })
  })

  return rows
}

export default function ReportSections({ result, query, script }) {
  const [view, setView] = useState("table")
  const [copied, setCopied] = useState(false)
  const rows = parseTable(result)

  const handleCopy = () => {
    navigator.clipboard.writeText(result)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="flex flex-col gap-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
        <div className="text-xs font-medium text-zinc-600 uppercase tracking-widest mb-2">
          Query
        </div>
        <div className="text-sm text-zinc-300 leading-relaxed">{query}</div>
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
          <div className="text-xs font-medium text-zinc-600 uppercase tracking-widest">
            Result
          </div>
          <div className="flex items-center gap-2">
            {rows && (
              <div className="flex bg-zinc-800 rounded-md p-0.5">
                {["table", "raw", "code"].map(v => (
                <button
                    key={v}
                    onClick={() => setView(v)}
                    className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                    view === v ? "bg-zinc-700 text-zinc-200" : "text-zinc-500 hover:text-zinc-300"
                    }`}
                >
                    {v === "table" ? "Table" : v === "raw" ? "Raw" : "Code"}
                </button>
                ))}
              </div>
            )}
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              <i className={`ti ${copied ? "ti-check text-green-400" : "ti-copy"} text-xs`} />
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
        </div>

        <div className="p-4">
          {rows && view === "table" ? (
            <div className="overflow-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr>
                    {rows[0].map((h, i) => (
                      <th key={i} className="text-left pb-3 pr-6 text-zinc-600 font-medium uppercase tracking-wider text-xs border-b border-zinc-800">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(1).map((row, i) => (
                    <tr key={i} className="border-b border-zinc-800/50 last:border-0 hover:bg-zinc-800/30 transition-colors">
                      {row.map((cell, j) => (
                        <td key={j} className={`py-2.5 pr-6 ${j === row.length - 1 ? "font-mono text-violet-400" : "text-zinc-400"}`}>
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : view === "code" ? (
            <pre className="text-xs text-zinc-400 font-mono leading-relaxed whitespace-pre-wrap overflow-auto max-h-80">
              {script ?? "No code available."}
            </pre>
          ) : (
            <pre className="text-xs text-zinc-400 font-mono leading-relaxed whitespace-pre-wrap overflow-auto max-h-80">
              {result}
            </pre>
          )}
        </div>
      </div>
</div>
  )
}