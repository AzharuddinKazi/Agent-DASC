import { useState } from "react"
import { submitTask } from "../../api"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { ArrowRight, CornerDownLeft, TrendingUp, Flag, BarChart3, ShieldCheck } from "lucide-react"

const SAMPLE_QUERIES = [
  "Show the top 5 LFIs by SAR volume this quarter.",
  "Identify entities with a high reversal ratio (>15%).",
  "Rank exchange houses by their composite risk score."
]

const CAPABILITIES = [
  { icon: TrendingUp,  label: "SAR Analysis"   },
  { icon: Flag,        label: "Risk Scoring"    },
  { icon: BarChart3,   label: "Entity Ranking"  },
  { icon: ShieldCheck, label: "AML Detection"   },
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
    } catch (err) {
      console.error(err)
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-background font-sans px-6">
      <div className="w-full max-w-[600px] flex flex-col gap-8">

        {/* Brand */}
        <div className="flex flex-col items-center gap-4 text-center">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-lg bg-foreground flex items-center justify-center shrink-0">
              <span className="text-xs font-black text-background leading-none">DS</span>
            </div>
            <span className="text-2xl font-bold text-foreground tracking-tight">
              DS<span className="text-brand">—</span>STAR
            </span>
          </div>

          {/* Capability pills — proper wrapping, no overflow */}
          <div className="flex flex-wrap justify-center gap-2">
            {CAPABILITIES.map(({ icon: Icon, label }) => (
              <Badge
                key={label}
                variant="outline"
                className="gap-1.5 rounded-full px-3 py-1 font-medium whitespace-nowrap"
                style={{ fontSize: '12px' }}
              >
                <Icon className="w-3.5 h-3.5 shrink-0" />
                {label}
              </Badge>
            ))}
          </div>
        </div>

        {/* Heading */}
        <div className="text-center">
          <h1 className="text-[2rem] font-bold text-foreground tracking-tight leading-tight mb-3">
            What do you want to analyse?
          </h1>
          <p className="text-[15px] text-muted-foreground leading-relaxed max-w-md mx-auto">
            Ask about LFI data, transaction flags, or risk exposure in plain English.
            The 7-agent pipeline handles the rest.
          </p>
        </div>

        {/* Input card — no pills inside, just textarea + submit */}
        <Card className="shadow-sm border-border focus-within:ring-2 focus-within:ring-ring/20 focus-within:border-foreground/30 transition-all">
          <CardContent className="p-0">
            <Textarea
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="e.g., Show me banks with more than 50 suspicious activity flags this quarter..."
              className="border-none bg-transparent shadow-none focus-visible:ring-0 resize-none px-5 pt-5 pb-3 text-[15px] rounded-b-none"
              style={{ minHeight: '120px' }}
              onKeyDown={e => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleRun() }
              }}
            />
            <Separator />
            <div className="flex items-center justify-between px-4 py-3 bg-muted/30 rounded-b-lg">
              <p className="text-[13px] text-muted-foreground">
                Press <kbd className="px-1.5 py-0.5 rounded border border-border bg-background font-mono text-[11px]">Enter</kbd> to run
              </p>
              <Button
                onClick={() => handleRun()}
                disabled={!query.trim() || isSubmitting}
                className="gap-2"
              >
                {isSubmitting ? "Running…" : (
                  <>
                    Analyse
                    <CornerDownLeft className="w-4 h-4 opacity-70" />
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Suggested queries — full-width rows, no truncation */}
        <div>
          <p className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground mb-3 px-1">
            Try these
          </p>
          <div className="flex flex-col gap-1">
            {SAMPLE_QUERIES.map((sq, idx) => (
              <button
                key={idx}
                onClick={() => handleRun(sq)}
                className="flex items-start gap-3 px-3 py-3 rounded-lg text-left text-[14px] text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors cursor-pointer w-full"
              >
                <ArrowRight className="w-4 h-4 shrink-0 mt-0.5 text-muted-foreground" />
                <span className="leading-snug">{sq}</span>
              </button>
            ))}
          </div>
        </div>

      </div>
    </div>
  )
}
