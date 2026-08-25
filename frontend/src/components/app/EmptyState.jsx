import { useState } from "react"
import { submitTask, clarifyTask } from "../../api"
import { brand } from "../../config/brand"
import { appendClarificationContext } from "../../lib/clarification"
import { useActiveDomainPack } from "../../hooks/useActiveDomainPack"
import { useFeatureFlags } from "../../hooks/useFeatureFlags"
import Sidebar from "./Sidebar"
import ClarifyingQuestionsModal from "./ClarifyingQuestionsModal"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from "@/components/ui/sheet"
import { Label } from "@/components/ui/label"
import { ArrowUp, ArrowRight, Menu, Package } from "lucide-react"

export default function EmptyState({ onSubmit, onDomainPacks, onData }) {
  const { pack: activePack } = useActiveDomainPack()
  // Same gate Sidebar.jsx uses for its nav link — this query-box status bar is a second,
  // independent entry point into the Domain Packs page (the "activate one"/"manage here"
  // links below), so it needs the same check or a non-admin can reach a page that's
  // supposed to be fully hidden while the feature is off.
  const { flags: featureFlags } = useFeatureFlags()
  const domainPacksEnabled = featureFlags.domain_packs !== false
  const [query, setQuery]               = useState("")
  const [mode, setMode]                 = useState("qa")   // "qa" | "report"
  const [requireHumanReview, setRequireHumanReview] = useState(false)   // report mode only
  const [isSubmitting, setIsSubmitting]           = useState(false)
  // Separate from isSubmitting so the button can say "Checking…" during the
  // clarify_task call (which can legitimately take up to 15s) rather than looking
  // identical to — or worse, indistinguishable from being stuck at — actual submission.
  const [isCheckingClarity, setIsCheckingClarity] = useState(false)
  const [error, setError]               = useState("")
  const [drawerOpen, setDrawerOpen]     = useState(false)
  const [clarifyState, setClarifyState] = useState(null)   // { query, type, questions, domainPackId } | null

  const doSubmit = async (q, type, domainPackId) => {
    setIsSubmitting(true)
    setError("")
    try {
      const res = await submitTask(q, "", type, type === "report" && requireHumanReview, domainPackId)
      onSubmit(q, res.data.task_id, type, type === "report" && requireHumanReview)
    } catch (err) {
      console.error(err)
      setError(err?.response?.data?.detail || err?.message || "Failed to submit — is the backend running?")
      setIsSubmitting(false)
    }
  }

  const handleRun = async (text, type = mode) => {
    const q = (typeof text === "string" ? text : query).trim()
    if (!q || isSubmitting || isCheckingClarity) return
    // Pinned once here, at the moment the user actually asks to run — not re-read later,
    // so a pack someone else activates/deactivates mid-flow (including during the
    // clarify round-trip below) can't change what this task ends up scoped to.
    const domainPackId = activePack?.id ?? null
    setIsCheckingClarity(true)
    setError("")
    try {
      const res = await clarifyTask(q, type, domainPackId)
      const questions = res.data.questions || []
      if (questions.length > 0) {
        setClarifyState({ query: q, type, questions, domainPackId })
        setIsCheckingClarity(false)
        return
      }
    } catch (err) {
      // Clarification is a nice-to-have, not a gate — if the endpoint errors or times
      // out, proceed straight to submission rather than blocking the user's actual
      // analysis on it.
      console.error("clarify_task failed, proceeding without it:", err)
    }
    setIsCheckingClarity(false)
    doSubmit(q, type, domainPackId)
  }

  const handleClarifyConfirm = (resolvedAnswers) => {
    const { query: q, type, domainPackId } = clarifyState
    setClarifyState(null)
    doSubmit(appendClarificationContext(q, resolvedAnswers), type, domainPackId)
  }

  const handleClarifySkip = () => {
    const { query: q, type, domainPackId } = clarifyState
    setClarifyState(null)
    doSubmit(q, type, domainPackId)
  }

  // Example queries for the active mode tab — Insight (qa) and Research (report) each
  // get their own set so switching tabs shows prompts that actually match what will run.
  const suggestions = brand.templates.filter(t => t.type === mode)

  const handleSelect = async (id, q, type) => {
    onSubmit(q, id, type || "qa")
  }

  return (
    <div className="h-screen flex bg-background overflow-hidden font-sans">

      {/* Permanent sidebar (desktop) */}
      <div className="hidden md:flex w-64 shrink-0 border-r border-border flex-col bg-sidebar">
        <Sidebar onNew={() => {}} currentTaskId={null} onSelect={handleSelect} onDomainPacks={onDomainPacks} onData={onData} />
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
              <SheetContent side="left" className="w-64 p-0 border-r border-border bg-sidebar" showCloseButton={false}>
                <SheetTitle className="sr-only">Navigation</SheetTitle>
                <Sidebar onNew={() => setDrawerOpen(false)} currentTaskId={null} onSelect={handleSelect} onDomainPacks={() => { onDomainPacks(); setDrawerOpen(false) }} onData={() => { onData(); setDrawerOpen(false) }} />
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

            {mode === "report" && (
              <Label className="text-caption text-muted-foreground cursor-pointer">
                <input
                  type="checkbox"
                  checked={requireHumanReview}
                  onChange={e => setRequireHumanReview(e.target.checked)}
                  className="w-3.5 h-3.5 rounded border-border accent-foreground cursor-pointer"
                />
                Require my review before finalizing each round
              </Label>
            )}

            <Card className="animated-border w-full shadow-sm border-border focus-within:ring-2 focus-within:ring-ring/20 focus-within:border-foreground/30 transition-all">
              <CardContent className="p-0">
                <Textarea
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  placeholder="e.g. Which entities have the highest value in [metric] relative to [metric] this quarter?"
                  className="border-none bg-transparent shadow-none focus-visible:ring-0 resize-none px-5 pt-4 pb-2 text-body text-foreground rounded-b-none"
                  style={{ minHeight: '56px' }}
                  onKeyDown={e => {
                    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleRun() }
                  }}
                />

                <Separator />
                {error && <p className="text-caption text-destructive px-5 pb-2 pt-2">{error}</p>}
                <div className="flex items-center justify-between px-4 py-3.5 bg-muted/30 rounded-b-lg">
                  {!domainPacksEnabled ? (
                    <span />
                  ) : activePack ? (
                    <span className="flex items-center gap-2 min-w-0">
                      <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-brand/30 bg-brand-tint text-brand-ink text-caption min-w-0">
                        <Package className="w-3 h-3 shrink-0" />
                        <span className="truncate">Using {activePack.name} domain</span>
                      </span>
                      <button onClick={onDomainPacks} className="hidden sm:inline text-label text-muted-foreground underline hover:text-foreground cursor-pointer shrink-0">
                        manage here
                      </button>
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5 text-caption text-muted-foreground">
                      <Package className="w-3 h-3" />
                      No active domain packs —{" "}
                      <button onClick={onDomainPacks} className="underline hover:text-foreground cursor-pointer">
                        activate one
                      </button>
                    </span>
                  )}
                  <Button onClick={() => handleRun()} disabled={!query.trim() || isSubmitting || isCheckingClarity} size="lg" className="gap-2 text-body px-4">
                    {isCheckingClarity ? "Checking…" : isSubmitting ? "Running…" : (<><ArrowUp className="size-5" />Analyse</>)}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {suggestions.length > 0 && (
              <div className="w-full">
                <p className="text-label font-semibold uppercase tracking-wider text-muted-foreground mb-2 px-1">
                  Try these
                </p>
                <div className="flex flex-col gap-1">
                  {suggestions.map((t, i) => (
                    <button
                      key={i}
                      onClick={() => handleRun(t.text, t.type)}
                      disabled={isSubmitting || isCheckingClarity}
                      className="group flex items-start gap-3 px-3 py-2.5 rounded-lg text-left text-caption text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <t.icon className="w-3.5 h-3.5 shrink-0 mt-0.5 text-brand" />
                      <span className="leading-snug">{t.text}</span>
                      <ArrowRight className="w-3.5 h-3.5 shrink-0 ml-auto mt-0.5 opacity-0 group-hover:opacity-100" />
                    </button>
                  ))}
                </div>
              </div>
            )}

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
