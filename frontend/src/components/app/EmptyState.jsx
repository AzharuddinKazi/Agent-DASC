import { useState } from "react"
import { submitTask } from "../../api"
import { ArrowRight } from "lucide-react"

const SAMPLE_QUERIES = [
  "Show the top 5 LFIs by SAR volume this quarter.",
  "Identify entities with a high reversal ratio (>15%).",
  "Rank exchange houses by their composite risk score."
]

export default function EmptyState({ onSubmit }) {
  const [query, setQuery] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleRun = async (text) => {
    const q = text || query
    if (!q.trim() || isSubmitting) return
    
    setIsSubmitting(true)
    try {
      const res = await submitTask(q)
      onSubmit(q, res.data.task_id)
    } catch (error) {
      console.error(error)
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-surface-subtle font-sans">
      <div className="w-full max-w-2xl flex flex-col gap-8">
        
        {/* Header */}
        <div className="flex flex-col items-center text-center gap-1.5">
          <div className="text-2xl font-semibold text-slate-900 tracking-tight">
            DS<span className="text-crimson-600 mx-[1px]">—</span>STAR
          </div>
          <div className="text-[9px] uppercase tracking-widest font-bold text-slate-400">
            Supervisory Intelligence
          </div>
        </div>

        {/* Main Content */}
        <div className="flex flex-col gap-6">
          <div className="text-center">
            <h1 className="text-2xl font-semibold text-slate-900 mb-2">What do you want to analyse?</h1>
            <p className="text-[14px] text-slate-400 max-w-md mx-auto leading-relaxed line-clamp-2">
              Ask questions about LFI data, transaction flags, or risk exposure in plain English.
            </p>
          </div>

          {/* Input Card */}
          <div className="bg-surface-base border border-slate-100 rounded-xl p-1 shadow-sm focus-within:border-crimson-500/50 transition-colors">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g., Show me banks with more than 50 suspicious activity flags..."
              className="w-full bg-transparent border-none outline-none resize-none p-4 text-[13px] text-slate-900 placeholder:text-slate-400 min-h-[100px] focus:ring-0 focus:border-none"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  handleRun()
                }
              }}
            />
            
            <div className="flex items-center justify-between px-3 pb-3">
              <div className="flex gap-2 overflow-hidden mr-2">
                {SAMPLE_QUERIES.slice(0, 2).map((sq, i) => (
                  <button 
                    key={i}
                    onClick={() => handleRun(sq)}
                    className="px-3 py-1.5 rounded-full border border-slate-100 text-[11px] text-slate-400 hover:text-slate-900 hover:bg-slate-050 transition-colors truncate max-w-[180px] cursor-pointer"
                  >
                    {sq}
                  </button>
                ))}
              </div>
              <button
                onClick={() => handleRun()}
                disabled={!query.trim() || isSubmitting}
                className="bg-crimson-600 hover:bg-crimson-500 text-white px-5 py-2 rounded-md text-[13px] font-medium disabled:opacity-50 disabled:bg-slate-200 disabled:text-slate-400 transition-colors cursor-pointer shrink-0 ml-auto"
              >
                Analyse
              </button>
            </div>
          </div>

          {/* Sample Query List Below */}
          <div className="flex flex-col gap-2 items-start pl-2">
            {SAMPLE_QUERIES.map((sq, idx) => (
              <button 
                key={idx} 
                onClick={() => handleRun(sq)}
                className="flex items-center gap-2 text-[13px] text-slate-600 hover:text-slate-900 transition-colors text-left cursor-pointer"
              >
                <ArrowRight className="w-3.5 h-3.5 text-crimson-600 shrink-0" />
                {sq}
              </button>
            ))}
          </div>
        </div>

      </div>
    </div>
  )
}