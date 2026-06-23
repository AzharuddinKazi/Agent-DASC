import { useState } from "react"
import { submitTask } from "../../api"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { ArrowRight, CornerDownLeft, TrendingUp, Flag, BarChart3, Shield } from "lucide-react"

const SAMPLE_QUERIES = [
  "Show the top 5 LFIs by SAR volume this quarter.",
  "Identify entities with a high reversal ratio (>15%).",
  "Rank exchange houses by their composite risk score."
]

const CAPABILITIES = [
  { icon: TrendingUp, label: "SAR Analysis" },
  { icon: Flag,       label: "Risk Scoring" },
  { icon: BarChart3,  label: "Entity Ranking" },
  { icon: Shield,     label: "AML Detection" },
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
    <div className="min-h-screen flex flex-col items-center justify-center relative overflow-hidden bg-background font-sans">
      {/* Dot-grid */}
      <div className="absolute inset-0 dot-grid opacity-50 pointer-events-none" />
      {/* Gradient blobs */}
      <div className="absolute -top-40 -left-40 w-[500px] h-[500px] rounded-full bg-crimson-050 blur-3xl pointer-events-none opacity-60" />
      <div className="absolute -bottom-40 -right-40 w-[400px] h-[400px] rounded-full bg-blue-050 blur-3xl pointer-events-none opacity-50" />

      <div className="relative z-10 w-full max-w-[600px] px-6 flex flex-col gap-8">

        {/* Brand */}
        <div className="flex flex-col items-center gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center shadow-md">
              <Shield className="w-5 h-5 text-primary-foreground" strokeWidth={2.5} />
            </div>
            <div>
              <div className="text-2xl font-extrabold text-foreground tracking-tight leading-none">
                DS<span className="text-primary">—</span>STAR
              </div>
              <div className="text-[9px] uppercase tracking-[0.18em] font-bold text-muted-foreground mt-0.5">
                Supervisory Intelligence
              </div>
            </div>
          </div>

          {/* Capability pills using shadcn Badge */}
          <div className="flex flex-wrap justify-center gap-2">
            {CAPABILITIES.map(({ icon: Icon, label }) => (
              <Badge key={label} variant="outline" className="gap-1.5 px-3 py-1 rounded-full text-[11px]">
                <Icon className="w-3 h-3 text-primary" />
                {label}
              </Badge>
            ))}
          </div>
        </div>

        {/* Main content */}
        <div className="flex flex-col gap-5">
          <div className="text-center">
            <h1 className="text-[28px] font-bold text-foreground tracking-tight leading-tight mb-2">
              What do you want to analyse?
            </h1>
            <p className="text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
              Ask about LFI data, transaction flags, or risk exposure in plain English.
            </p>
          </div>

          {/* Input card using shadcn Card */}
          <Card className="shadow-md border-border focus-within:ring-2 focus-within:ring-ring/30 focus-within:border-primary/50 transition-all">
            <CardContent className="p-0">
              <Textarea
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="e.g., Show me banks with more than 50 suspicious activity flags..."
                className="border-none bg-transparent shadow-none focus-visible:ring-0 resize-none px-4 pt-4 pb-2 min-h-[110px] text-sm rounded-b-none"
                onKeyDown={e => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault()
                    handleRun()
                  }
                }}
              />
              <Separator />
              <div className="flex items-center justify-between px-3 py-2.5 bg-muted/40 rounded-b-lg">
                <div className="flex gap-2 overflow-hidden mr-2">
                  {SAMPLE_QUERIES.slice(0, 2).map((sq, i) => (
                    <Button
                      key={i}
                      variant="outline"
                      size="sm"
                      onClick={() => handleRun(sq)}
                      className="rounded-full text-[11px] h-6 px-3 truncate max-w-[180px]"
                    >
                      {sq}
                    </Button>
                  ))}
                </div>
                <Button
                  onClick={() => handleRun()}
                  disabled={!query.trim() || isSubmitting}
                  size="lg"
                  className="gap-1.5 shrink-0"
                >
                  {isSubmitting ? (
                    <>
                      <span className="w-2 h-2 rounded-full bg-primary-foreground/70 animate-pulse" />
                      Running…
                    </>
                  ) : (
                    <>
                      Analyse
                      <CornerDownLeft className="w-3.5 h-3.5 opacity-70" />
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Suggested queries */}
          <div className="flex flex-col gap-1">
            <p className="text-[10px] uppercase tracking-widest font-bold text-muted-foreground px-1 mb-1">
              Try these
            </p>
            {SAMPLE_QUERIES.map((sq, idx) => (
              <Button
                key={idx}
                variant="ghost"
                onClick={() => handleRun(sq)}
                className="justify-start gap-2.5 h-auto py-2.5 px-3 text-left font-normal text-sm text-foreground"
              >
                <span className="w-5 h-5 rounded-md bg-crimson-050 border border-crimson-100 flex items-center justify-center shrink-0">
                  <ArrowRight className="w-3 h-3 text-primary" />
                </span>
                <span className="leading-snug">{sq}</span>
              </Button>
            ))}
          </div>
        </div>

        <p className="text-center text-[11px] text-muted-foreground">
          Powered by a 7-agent autonomous analysis pipeline
        </p>
      </div>
    </div>
  )
}
