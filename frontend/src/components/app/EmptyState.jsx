import { useState } from "react"
import { submitTask, getTasks } from "../../api"
import Sidebar from "./Sidebar"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from "@/components/ui/sheet"
import {
  ArrowUp, TrendingUp, Flag, BarChart3, ShieldCheck, Info,
  Paperclip, SlidersHorizontal, Menu, BarChart2, AlertTriangle,
  FileText, BookOpen, Search,
} from "lucide-react"

const CAPABILITIES = [
  { icon: TrendingUp,  label: "SAR Analysis"  },
  { icon: Flag,        label: "Risk Scoring"   },
  { icon: BarChart3,   label: "Entity Ranking" },
  { icon: ShieldCheck, label: "AML Detection"  },
]

const TEMPLATES = [
  { icon: BarChart2,      color: "blue",   type: "qa",     text: "Which LFIs have the highest card fraud loss rate vs. the peer median this quarter?" },
  { icon: TrendingUp,     color: "blue",   type: "qa",     text: "Show me fraud typology trends by channel across UAE banks over the past 12 months." },
  { icon: AlertTriangle,  color: "blue",   type: "qa",     text: "Which LFIs are statistical outliers in their social engineering fraud detection rate?" },
  { icon: FileText,       color: "purple", type: "report", text: "Generate a thematic analysis of APP fraud growth across UAE banks in 2024." },
  { icon: BookOpen,       color: "purple", type: "report", text: "Produce a sector-wide fraud trend report for H1 2025 suitable for a supervisory letter annex." },
  { icon: Search,         color: "amber",  type: "qa",     text: "Which LFIs have declining STR filing rates compared to the prior quarter?" },
]

const ICON_BG = {
  blue:   "bg-blue-50 text-blue-600",
  purple: "bg-purple-50 text-purple-600",
  amber:  "bg-amber-50 text-amber-600",
}

export default function EmptyState({ onSubmit }) {
  const [query, setQuery]               = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError]               = useState("")
  const [showAttach, setShowAttach]     = useState(false)
  const [showFormat, setShowFormat]     = useState(false)
  const [drawerOpen, setDrawerOpen]     = useState(false)

  const handleRun = async (text, type = "qa") => {
    const q = (typeof text === "string" ? text : query).trim()
    if (!q || isSubmitting) return
    setIsSubmitting(true)
    setError("")
    try {
      const res = await submitTask(q, "", type)
      onSubmit(q, res.data.task_id, type)
    } catch (err) {
      console.error(err)
      setError(err?.response?.data?.detail || err?.message || "Failed to submit — is the backend running?")
      setIsSubmitting(false)
    }
  }

  const handleSelect = async (id, q, type) => {
    onSubmit(q, id, type || "qa")
  }

  return (
    <div className="h-screen flex bg-background overflow-hidden font-sans">

      {/* Permanent sidebar (desktop) */}
      <div className="hidden md:flex w-[240px] shrink-0 border-r border-border flex-col bg-sidebar">
        <Sidebar onNew={() => {}} currentTaskId={null} onSelect={handleSelect} />
      </div>

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">

        {/* Top bar */}
        <div className="h-14 border-b border-border bg-card flex items-center justify-between px-4 shrink-0">
          <div className="flex items-center gap-3">
            <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="md:hidden shrink-0">
                  <Menu className="w-4 h-4" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-[240px] p-0 border-r border-border bg-sidebar" showCloseButton={false}>
                <SheetTitle className="sr-only">Navigation</SheetTitle>
                <Sidebar onNew={() => setDrawerOpen(false)} currentTaskId={null} onSelect={handleSelect} />
              </SheetContent>
            </Sheet>
            <h1 className="text-[15px] font-bold text-foreground leading-none">New Analysis</h1>
          </div>
        </div>

        {/* Chat area */}
        <div className="flex-1 overflow-y-auto flex flex-col items-center px-6 py-12">
          <div className="w-full max-w-[720px] flex flex-col gap-6 items-center">

            <div className="flex flex-wrap justify-center gap-2">
              {CAPABILITIES.map(({ icon: Icon, label }) => (
                <Badge key={label} variant="outline" className="gap-1.5 rounded-full px-3 py-1 font-medium whitespace-nowrap text-xs">
                  <Icon className="w-3.5 h-3.5 shrink-0" />
                  {label}
                </Badge>
              ))}
            </div>

            <div className="text-center">
              <h2 className="text-[1.75rem] font-bold text-foreground tracking-tight leading-tight mb-2">
                What would you like to analyse?
              </h2>
              <p className="text-[14px] text-muted-foreground leading-relaxed max-w-lg mx-auto">
                Ask a question about LFI data in plain English. FIP will plan, code, and verify the answer automatically.
              </p>
            </div>

            <Card className="w-full shadow-sm border-border focus-within:ring-2 focus-within:ring-ring/20 focus-within:border-foreground/30 transition-all">
              <CardContent className="p-0">
                <Textarea
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  placeholder="e.g. Which LFIs have the highest card fraud loss rate relative to transaction volume in Q1 2025?"
                  className="border-none bg-transparent shadow-none focus-visible:ring-0 resize-none px-5 pt-5 pb-3 text-[15px] rounded-b-none"
                  style={{ minHeight: '110px' }}
                  onKeyDown={e => {
                    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleRun() }
                  }}
                />

                {showAttach && (
                  <div className="px-4 pb-3">
                    <Separator className="mb-3" />
                    <p className="text-xs font-semibold text-foreground mb-2">Attach files</p>
                    <div className="border border-dashed border-border rounded-lg py-6 text-center">
                      <p className="text-xs text-muted-foreground">
                        Drop files here or <span className="text-foreground underline cursor-pointer">browse</span>
                      </p>
                      <p className="text-[11px] text-muted-foreground mt-1">CSV, Excel, JSON, PDF · up to 500 MB per file</p>
                      <p className="text-[10px] text-muted-foreground/70 mt-1">Files are stored in your workspace and never leave CBUAE infrastructure</p>
                    </div>
                  </div>
                )}

                {showFormat && (
                  <div className="px-4 pb-3">
                    <Separator className="mb-3" />
                    <p className="text-xs font-semibold text-foreground mb-2">Output formatting</p>
                    <div className="grid grid-cols-3 gap-3 text-xs">
                      {[
                        { label: "Output style", opts: ["Auto", "Table", "Bullet summary", "Narrative"] },
                        { label: "Number format", opts: ["Auto", "AED", "Percentage", "Index"] },
                        { label: "Include charts", opts: ["Auto", "Always", "Never"] },
                      ].map(g => (
                        <div key={g.label}>
                          <p className="text-[10px] text-muted-foreground mb-1.5">{g.label}</p>
                          <div className="flex flex-wrap gap-1">
                            {g.opts.map((o, i) => (
                              <span key={o} className={`px-2 py-1 rounded border text-[10px] ${i === 0 ? "bg-foreground text-background border-foreground" : "border-border text-muted-foreground"}`}>{o}</span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <Separator />
                {error && <p className="text-[12px] text-destructive px-5 pb-2 pt-2">{error}</p>}
                <div className="flex items-center justify-between px-4 py-3 bg-muted/30 rounded-b-lg">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => { setShowAttach(v => !v); setShowFormat(false) }}
                      className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors ${showAttach ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-accent/60"}`}
                    >
                      <Paperclip className="w-3.5 h-3.5" /> Attach files
                    </button>
                    <button
                      onClick={() => { setShowFormat(v => !v); setShowAttach(false) }}
                      className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors ${showFormat ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-accent/60"}`}
                    >
                      <SlidersHorizontal className="w-3.5 h-3.5" /> Formatting
                    </button>
                  </div>
                  <Button onClick={() => handleRun()} disabled={!query.trim() || isSubmitting} className="gap-2">
                    {isSubmitting ? "Running…" : (<><ArrowUp className="w-4 h-4" />Analyse</>)}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Template grid */}
            <div className="w-full">
              <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-2.5 px-1">
                Start with a template
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {TEMPLATES.map((t, i) => {
                  const Icon = t.icon
                  return (
                    <button
                      key={i}
                      onClick={() => handleRun(t.text, t.type)}
                      className="text-left p-3.5 rounded-lg border border-border bg-card hover:border-foreground/20 hover:shadow-sm transition-all cursor-pointer"
                    >
                      <div className={`w-6 h-6 rounded-[5px] flex items-center justify-center mb-2 ${ICON_BG[t.color]}`}>
                        <Icon className="w-3.5 h-3.5" />
                      </div>
                      <p className="text-xs text-muted-foreground leading-snug">{t.text}</p>
                    </button>
                  )
                })}
              </div>
            </div>

            <p className="text-[11px] text-muted-foreground/70 text-center pt-2">
              FIP · Financial Intelligence Platform · CBUAE Internal · Air-gapped
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
