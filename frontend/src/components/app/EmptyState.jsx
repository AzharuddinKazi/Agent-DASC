import { useState } from "react"
import { submitTask } from "../../api"
import { ArrowRight, CornerDownLeft, TrendingUp, Flag, BarChart3, Shield } from "lucide-react"

const SAMPLE_QUERIES = [
  "Show the top 5 LFIs by SAR volume this quarter.",
  "Identify entities with a high reversal ratio (>15%).",
  "Rank exchange houses by their composite risk score."
]

const CAPABILITIES = [
  { icon: TrendingUp, label: "SAR Analysis" },
  { icon: Flag, label: "Risk Scoring" },
  { icon: BarChart3, label: "Entity Ranking" },
  { icon: Shield, label: "AML Detection" },
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
    <div className="min-h-screen flex flex-col items-center justify-center relative overflow-hidden bg-surface-subtle font-sans">

      {/* Dot-grid background */}
      <div className="absolute inset-0 dot-grid opacity-60 pointer-events-none" />

      {/* Top-left gradient blob */}
      <div className="absolute -top-40 -left-40 w-[600px] h-[600px] rounded-full bg-gradient-to-br from-crimson-050 via-crimson-100/30 to-transparent blur-3xl pointer-events-none opacity-70" />
      {/* Bottom-right gradient blob */}
      <div className="absolute -bottom-40 -right-40 w-[500px] h-[500px] rounded-full bg-gradient-to-tl from-blue-050 via-blue-100/20 to-transparent blur-3xl pointer-events-none opacity-60" />

      <div className="relative z-10 w-full max-w-[640px] px-6 flex flex-col gap-10">

        {/* Brand */}
        <div className="flex flex-col items-center gap-3">
          <div className="flex items-center gap-2">
            {/* Logo mark */}
            <div className="w-9 h-9 rounded-lg bg-crimson-600 flex items-center justify-center shadow-card-md">
              <Shield className="w-5 h-5 text-white" strokeWidth={2.5} />
            </div>
            <div>
              <div className="text-2xl font-extrabold text-slate-900 tracking-tight leading-none">
                DS<span className="text-crimson-600">—</span>STAR
              </div>
              <div className="text-[9px] uppercase tracking-[0.18em] font-bold text-slate-400 leading-tight mt-0.5">
                Supervisory Intelligence
              </div>
            </div>
          </div>

          {/* Capability pills */}
          <div className="flex items-center gap-2 flex-wrap justify-center mt-1">
            {CAPABILITIES.map(({ icon: Icon, label }) => (
              <div
                key={label}
                className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-base border border-slate-100 text-[11px] font-medium text-slate-500 shadow-card"
              >
                <Icon className="w-3 h-3 text-crimson-500" />
                {label}
              </div>
            ))}
          </div>
        </div>

        {/* Main Content */}
        <div className="flex flex-col gap-5">
          <div className="text-center">
            <h1 className="text-[28px] font-bold text-slate-900 tracking-tight leading-tight mb-2">
              What do you want to analyse?
            </h1>
            <p className="text-[14px] text-slate-500 max-w-md mx-auto leading-relaxed">
              Ask about LFI data, transaction flags, or risk exposure in plain English. The pipeline handles the rest.
            </p>
          </div>

          {/* Input Card */}
          <div className="bg-surface-base border border-slate-200 rounded-xl shadow-card-md overflow-hidden transition-all duration-200 focus-within:border-crimson-500/60 focus-within:glow-ring group">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g., Show me banks with more than 50 suspicious activity flags..."
              className="w-full bg-transparent border-none outline-none resize-none px-4 pt-4 pb-2 text-[14px] text-slate-900 placeholder:text-slate-400 min-h-[110px] focus:ring-0 leading-relaxed"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  handleRun()
                }
              }}
            />

            {/* Input footer bar */}
            <div className="flex items-center justify-between px-3 pb-3 pt-1 border-t border-slate-100 bg-slate-050/50">
              <div className="flex gap-2 overflow-hidden mr-2">
                {SAMPLE_QUERIES.slice(0, 2).map((sq, i) => (
                  <button
                    key={i}
                    onClick={() => handleRun(sq)}
                    className="px-2.5 py-1 rounded-full border border-slate-200 text-[11px] text-slate-500 hover:text-slate-900 hover:border-slate-300 hover:bg-surface-base transition-all truncate max-w-[185px] cursor-pointer font-medium"
                  >
                    {sq}
                  </button>
                ))}
              </div>

              <button
                onClick={() => handleRun()}
                disabled={!query.trim() || isSubmitting}
                className="flex items-center gap-1.5 bg-crimson-600 hover:bg-crimson-700 text-white px-4 py-2 rounded-lg text-[13px] font-semibold disabled:opacity-40 disabled:bg-slate-200 disabled:text-slate-400 transition-all cursor-pointer shrink-0 shadow-sm hover:shadow-card active:scale-[0.98]"
              >
                {isSubmitting ? (
                  <>
                    <span className="w-2 h-2 rounded-full bg-white/70 animate-pulse" />
                    Running…
                  </>
                ) : (
                  <>
                    Analyse
                    <CornerDownLeft className="w-3.5 h-3.5 opacity-70" />
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Suggested Queries */}
          <div className="flex flex-col gap-1.5">
            <div className="text-[10px] uppercase tracking-widest font-bold text-slate-400 px-1 mb-1">
              Try these
            </div>
            {SAMPLE_QUERIES.map((sq, idx) => (
              <button
                key={idx}
                onClick={() => handleRun(sq)}
                className="flex items-center gap-2.5 text-[13px] text-slate-600 hover:text-slate-900 hover:bg-surface-base border border-transparent hover:border-slate-100 rounded-lg px-3 py-2 transition-all text-left cursor-pointer group/item shadow-[0_0_0_0] hover:shadow-card"
              >
                <div className="w-5 h-5 rounded-md bg-crimson-050 border border-crimson-100 flex items-center justify-center shrink-0 group-hover/item:bg-crimson-100 transition-colors">
                  <ArrowRight className="w-3 h-3 text-crimson-600" />
                </div>
                <span className="leading-snug">{sq}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Footer note */}
        <div className="text-center text-[11px] text-slate-400 font-medium">
          Powered by a 7-agent autonomous analysis pipeline
        </div>

      </div>
    </div>
  )
}
