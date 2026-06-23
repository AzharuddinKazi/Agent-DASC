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
    <div className="min-h-screen flex flex-col items-center justify-center bg-background font-sans px-4">
      <div className="w-full max-w-[560px] flex flex-col gap-8">

        {/* Brand */}
        <div className="flex flex-col items-center gap-4 text-center">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-foreground flex items-center justify-center">
              <span className="text-[11px] font-black text-background leading-none">DS</span>
            </div>
            <span className="text-xl font-bold text-foreground tracking-tight">
              DS<span className="text-brand">—</span>STAR
            </span>
          </div>
          <div className="flex flex-wrap justify-center gap-2">
            {CAPABILITIES.map(({ icon: Icon, label }) => (
              <Badge key={label} variant="outline" className="gap-1.5 rounded-full text-xs px-3 py-1 font-medium">
                <Icon className="w-3 h-3" />
                {label}
              </Badge>
            ))}
          </div>
        </div>

        {/* Heading */}
        <div className="text-center">
          <h1 className="text-3xl font-bold text-foreground tracking-tight mb-2">
            What do you want to analyse?
          </h1>
          <p className="text-sm text-muted-foreground leading-relaxed max-w-md mx-auto">
            Ask about LFI data, transaction flags, or risk exposure in plain English.
            The 7-agent pipeline handles the rest.
          </p>
        </div>

        {/* Input card */}
        <Card className="shadow-sm border-border focus-within:ring-2 focus-within:ring-ring/20 focus-within:border-foreground/30 transition-all">
          <CardContent className="p-0">
            <Textarea
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="e.g., Show me banks with more than 50 suspicious activity flags this quarter..."
              className="border-none bg-transparent shadow-none focus-visible:ring-0 resize-none px-4 pt-4 pb-2 min-h-[110px] text-sm rounded-b-none"
              onKeyDown={e => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleRun() }
              }}
            />
            <Separator />
            <div className="flex items-center justify-between px-3 py-2.5 bg-muted/30 rounded-b-lg">
              <div className="flex gap-2 overflow-hidden mr-2">
                {SAMPLE_QUERIES.slice(0, 2).map((sq, i) => (
                  <Button key={i} variant="outline" size="sm" onClick={() => handleRun(sq)}
                    className="rounded-full text-xs h-6 px-3 truncate max-w-[185px]">
                    {sq}
                  </Button>
                ))}
              </div>
              <Button onClick={() => handleRun()} disabled={!query.trim() || isSubmitting} className="gap-1.5 shrink-0">
                {isSubmitting ? "Running…" : <><span>Analyse</span><CornerDownLeft className="w-3.5 h-3.5 opacity-60" /></>}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Suggested queries */}
        <div>
          <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-2">
            Try these
          </p>
          <div className="flex flex-col gap-0.5">
            {SAMPLE_QUERIES.map((sq, idx) => (
              <Button key={idx} variant="ghost" onClick={() => handleRun(sq)}
                className="justify-start gap-3 h-auto py-2.5 font-normal text-sm text-muted-foreground hover:text-foreground text-left">
                <ArrowRight className="w-3.5 h-3.5 shrink-0 text-muted-foreground" />
                {sq}
              </Button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
