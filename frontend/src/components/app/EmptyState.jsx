import { useState } from "react"
import { submitTask, clarifyTask } from "../../api"
import { brand } from "../../config/brand"
import { appendClarificationContext } from "../../lib/clarification"
import Sidebar from "./Sidebar"
import ClarifyingQuestionsModal from "./ClarifyingQuestionsModal"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from "@/components/ui/sheet"
import { ArrowUp, Paperclip, SlidersHorizontal, Menu } from "lucide-react"

export default function EmptyState({ onSubmit, onDomainPacks }) {
  const [query, setQuery]               = useState("")
  const [mode, setMode]                 = useState("qa")   // "qa" | "report"
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError]               = useState("")
  const [showAttach, setShowAttach]     = useState(false)
  const [showFormat, setShowFormat]     = useState(false)
  const [drawerOpen, setDrawerOpen]     = useState(false)
  const [clarifyState, setClarifyState] = useState(null)   // { query, type, questions } | null

  const doSubmit = async (q, type) => {
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

  const handleRun = async (text, type = mode) => {
    const q = (typeof text === "string" ? text : query).trim()
    if (!q || isSubmitting) return
    setIsSubmitting(true)
    setError("")
    try {
      const res = await clarifyTask(q, type)
      const questions = res.data.questions || []
      if (questions.length > 0) {
        setClarifyState({ query: q, type, questions })
        setIsSubmitting(false)
        return
      }
    } catch (err) {
      // Clarification is a nice-to-have, not a gate — if the endpoint errors, proceed
      // straight to submission rather than blocking the user's actual analysis on it.
      console.error("clarify_task failed, proceeding without it:", err)
    }
    doSubmit(q, type)
  }

  const handleClarifyConfirm = (resolvedAnswers) => {
    const { query: q, type } = clarifyState
    setClarifyState(null)
    doSubmit(appendClarificationContext(q, resolvedAnswers), type)
  }

  const handleClarifySkip = () => {
    const { query: q, type } = clarifyState
    setClarifyState(null)
    doSubmit(q, type)
  }

  const handleSelect = async (id, q, type) => {
    onSubmit(q, id, type || "qa")
  }

  return (
    <div className="h-screen flex bg-background overflow-hidden font-sans">

      {/* Permanent sidebar (desktop) */}
      <div className="hidden md:flex w-60 shrink-0 border-r border-border flex-col bg-sidebar">
        <Sidebar onNew={() => {}} currentTaskId={null} onSelect={handleSelect} onDomainPacks={onDomainPacks} />
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
              <SheetContent side="left" className="w-60 p-0 border-r border-border bg-sidebar" showCloseButton={false}>
                <SheetTitle className="sr-only">Navigation</SheetTitle>
                <Sidebar onNew={() => setDrawerOpen(false)} currentTaskId={null} onSelect={handleSelect} onDomainPacks={() => { onDomainPacks(); setDrawerOpen(false) }} />
              </SheetContent>
            </Sheet>
            <h1 className="text-heading text-foreground leading-none">New Analysis</h1>
          </div>
        </div>

        {/* Chat area */}
        <div className="flex-1 overflow-y-auto flex flex-col items-center justify-center px-6 py-12">
          <div className="w-full max-w-[720px] flex flex-col gap-6 items-center">

            <div className="flex flex-wrap items-center justify-center divide-x divide-border">
              {brand.capabilities.map(({ icon: Icon, label }) => (
                <span key={label} className="flex items-center gap-1.5 px-3 first:pl-0 last:pr-0 text-label uppercase text-muted-foreground">
                  <Icon className="w-3 h-3 text-brand shrink-0" />
                  {label}
                </span>
              ))}
            </div>

            <div className="text-center">
              <h2 className="text-display-sm text-foreground tracking-tight mb-2">
                What would you like to analyse?
              </h2>
              <p className="text-body text-muted-foreground leading-relaxed max-w-lg mx-auto">
                Ask a question about your data in plain English. {brand.appName} will plan, code, and verify the answer automatically.
              </p>
            </div>

            <div role="tablist" aria-label="Analysis mode" className="inline-flex items-center gap-0.5 p-1 rounded-lg bg-muted/60 border border-border">
              {["qa", "report"].map(m => (
                <button
                  key={m}
                  role="tab"
                  aria-selected={mode === m}
                  onClick={() => setMode(m)}
                  className={`px-4 py-1.5 rounded-md text-caption font-medium transition-colors cursor-pointer ${
                    mode === m ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {brand.modeLabels[m]}
                </button>
              ))}
            </div>

            <Card className="w-full shadow-sm border-border focus-within:ring-2 focus-within:ring-ring/20 focus-within:border-foreground/30 transition-all">
              <CardContent className="p-0">
                <Textarea
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  placeholder="e.g. Which entities have the highest value in [metric] relative to [metric] this quarter?"
                  className="border-none bg-transparent shadow-none focus-visible:ring-0 resize-none px-5 pt-5 pb-3 text-prompt md:text-prompt text-foreground rounded-b-none"
                  style={{ minHeight: '110px' }}
                  onKeyDown={e => {
                    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleRun() }
                  }}
                />

                {showAttach && (
                  <div className="px-4 pb-3">
                    <Separator className="mb-3" />
                    <p className="text-caption font-semibold text-foreground mb-2">Attach files</p>
                    <div className="border border-dashed border-border rounded-lg py-6 text-center">
                      <p className="text-caption text-muted-foreground">
                        Drop files here or <span className="text-foreground underline cursor-pointer">browse</span>
                      </p>
                      <p className="text-label text-muted-foreground mt-1">CSV, Excel, JSON, PDF · up to 500 MB per file</p>
                      <p className="text-label text-muted-foreground/70 mt-1">Files are stored in your workspace and never leave this deployment</p>
                    </div>
                  </div>
                )}

                {showFormat && (
                  <div className="px-4 pb-3">
                    <Separator className="mb-3" />
                    <p className="text-caption font-semibold text-foreground mb-2">Output formatting</p>
                    <div className="grid grid-cols-3 gap-3 text-caption">
                      {[
                        { label: "Output style", opts: ["Auto", "Table", "Bullet summary", "Narrative"] },
                        { label: "Number format", opts: ["Auto", "Currency", "Percentage", "Index"] },
                        { label: "Include charts", opts: ["Auto", "Always", "Never"] },
                      ].map(g => (
                        <div key={g.label}>
                          <p className="text-label text-muted-foreground mb-1.5">{g.label}</p>
                          <div className="flex flex-wrap gap-1">
                            {g.opts.map((o, i) => (
                              <span key={o} className={`px-2 py-1 rounded border text-label ${i === 0 ? "bg-foreground text-background border-foreground" : "border-border text-muted-foreground"}`}>{o}</span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <Separator />
                {error && <p className="text-caption text-destructive px-5 pb-2 pt-2">{error}</p>}
                <div className="flex items-center justify-between px-4 py-3.5 bg-muted/30 rounded-b-lg">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => { setShowAttach(v => !v); setShowFormat(false) }}
                      className={`flex items-center gap-2 px-3 py-2 rounded-md text-body font-medium transition-colors ${showAttach ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-accent/60"}`}
                    >
                      <Paperclip className="w-4 h-4" /> Attach files
                    </button>
                    <button
                      onClick={() => { setShowFormat(v => !v); setShowAttach(false) }}
                      className={`flex items-center gap-2 px-3 py-2 rounded-md text-body font-medium transition-colors ${showFormat ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-accent/60"}`}
                    >
                      <SlidersHorizontal className="w-4 h-4" /> Formatting
                    </button>
                  </div>
                  <Button onClick={() => handleRun()} disabled={!query.trim() || isSubmitting} size="lg" className="gap-2 text-body px-4">
                    {isSubmitting ? "Running…" : (<><ArrowUp className="size-5" />Analyse</>)}
                  </Button>
                </div>
              </CardContent>
            </Card>

            <p className="text-label text-muted-foreground/70 text-center pt-2">
              {brand.footerText}
            </p>
          </div>
        </div>
      </div>

      <ClarifyingQuestionsModal
        open={!!clarifyState}
        questions={clarifyState?.questions || []}
        onConfirm={handleClarifyConfirm}
        onSkip={handleClarifySkip}
      />
    </div>
  )
}
