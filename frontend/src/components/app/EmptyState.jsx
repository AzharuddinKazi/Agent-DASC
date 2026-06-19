import { useState } from "react"
import { submitTask } from "@/api"

const SAMPLES = [
  "Top 5 LFIs by fraud amount broken down by fraud type",
  "Which emirate has the highest reversed transaction ratio?",
  "Rank all LFIs by composite risk score",
  "Compare fraud rates across LFI types",
]

export default function EmptyState({ onSubmit }) {
  const [query, setQuery]   = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError]   = useState(null)

  const handleRun = async () => {
    if (!query.trim()) return
    setLoading(true); setError(null)
    try {
      const res = await submitTask(query.trim(), "")
      onSubmit(query.trim(), res.data.task_id)
    } catch {
      setError("Could not reach the API. Is the backend running?")
      setLoading(false)
    }
  }

  const handleKey = (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleRun()
  }

  return (
    <div className="min-h-screen bg-[#09090B] flex flex-col items-center justify-center px-6">
      <div className="w-full max-w-2xl flex flex-col items-center">

        <div className="w-11 h-11 rounded-xl bg-violet-600 flex items-center justify-center text-white font-medium text-sm mb-6">
          DS
        </div>

        <h1 className="text-3xl font-medium text-zinc-100 tracking-tight mb-3">
          What do you want to analyse?
        </h1>
        <p className="text-sm text-zinc-500 text-center mb-10 leading-relaxed">
          Ask a question about your financial data in plain English.<br />
          DS-STAR will plan, code, execute and verify the answer.
        </p>

        <div className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl p-4 flex flex-col gap-3">
          <textarea
            rows={3}
            className="w-full bg-transparent text-sm text-zinc-200 placeholder-zinc-600 outline-none resize-none leading-relaxed"
            placeholder="e.g. Which LFIs have the highest fraud rate, broken down by fraud type?"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKey}
          />
          <div className="flex items-center justify-between">
            <div className="flex gap-2 flex-wrap">
              {SAMPLES.slice(0, 2).map(s => (
                <button
                  key={s}
                  onClick={() => setQuery(s)}
                  className="text-xs text-zinc-500 border border-zinc-800 rounded-full px-3 py-1 hover:text-zinc-300 hover:border-zinc-600 transition-colors"
                >
                  {s.slice(0, 32)}…
                </button>
              ))}
            </div>
            <button
              onClick={handleRun}
              disabled={!query.trim() || loading}
              className="bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white text-xs font-medium rounded-lg px-4 py-2 flex items-center gap-2 transition-colors"
            >
              <i className="ti ti-player-play text-sm" />
              {loading ? "Starting..." : "Analyse"}
            </button>
          </div>
        </div>

        {error && <p className="text-xs text-red-400 mt-3">{error}</p>}

        <div className="mt-8 flex flex-col gap-2 w-full">
          {SAMPLES.map(s => (
            <button
              key={s}
              onClick={() => setQuery(s)}
              className="text-left text-xs text-zinc-600 hover:text-zinc-400 transition-colors py-1 flex items-center gap-2"
            >
              <i className="ti ti-arrow-right text-xs" />
              {s}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}