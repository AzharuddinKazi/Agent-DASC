import { useState, useEffect } from "react"
import { getTask, submitTask, clarifyTask, stopTask, pauseTask, resumeTask, submitReviewDecision } from "../../api"
import { brand } from "../../config/brand"
import { appendClarificationContext } from "../../lib/clarification"
import { statusMeta } from "../../lib/taskStatus"
import Sidebar from "./Sidebar"
import ReportPanel from "./ReportPanel"
import ClarifyingQuestionsModal from "./ClarifyingQuestionsModal"
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Menu, Pause, Play, Square, RotateCcw } from "lucide-react"

export default function Dashboard({ query, taskId, taskType: initialTaskType, requireHumanReview = false, onNew, onDomainPacks, onData }) {
  const [task, setTask]                 = useState(null)
  const [activeQuery, setActiveQuery]   = useState(query)
  const [activeTaskId, setActiveTaskId] = useState(taskId)
  const [activeTaskType, setActiveTaskType] = useState(initialTaskType || "qa")
  const [drawerOpen, setDrawerOpen]     = useState(false)
  const [clarifyState, setClarifyState] = useState(null)   // { text, type, questions } | null
  const [isStopping, setIsStopping]     = useState(false)
  const [isPausing, setIsPausing]       = useState(false)
  const [isResuming, setIsResuming]     = useState(false)
  const [isRerunning, setIsRerunning]   = useState(false)
  const [isReviewSubmitting, setIsReviewSubmitting] = useState(false)
  // Same reasoning as EmptyState's isCheckingClarity — clarify_task can legitimately
  // take up to 15s; the follow-up bar needs its own "Checking…" state instead of
  // looking stuck, distinct from a task actually running.
  const [isCheckingClarity, setIsCheckingClarity] = useState(false)
  // Polling stops once status leaves "running" (including on pause) — Resume needs a
  // way to restart it without changing activeTaskId (same task, just running again),
  // so it bumps this to re-trigger the effect below.
  const [pollGeneration, setPollGeneration] = useState(0)

  useEffect(() => {
    if (!activeTaskId) return
    setTask(null)
    setIsStopping(false)
    setIsPausing(false)
    setIsResuming(false)
    setIsRerunning(false)
    setIsReviewSubmitting(false)
    const poll = async () => {
      try {
        const r = await getTask(activeTaskId)
        setTask(r.data)
        if (r.data.status !== "running") clearInterval(interval)
      } catch (err) { console.error(err) }
    }
    poll()
    const interval = setInterval(poll, 2000)
    return () => clearInterval(interval)
  }, [activeTaskId, pollGeneration])

  const handleSelect = (id, q, type) => { setActiveTaskId(id); setActiveQuery(q); if (type) setActiveTaskType(type); setDrawerOpen(false) }

  const handleStop = async () => {
    if (isStopping) return
    const wasAwaitingReview = task?.status === "awaiting_review"
    setIsStopping(true)
    try {
      await stopTask(activeTaskId)
      // Cancellation is cooperative (see backend/agents/cancellation.py) — it takes
      // effect at the next safe point, not instantly, so the regular 2s poll picks up
      // the eventual status:"stopped" rather than this handler flipping it optimistically.
      // Exception: from "awaiting_review" there's no in-flight graph run for a cooperative
      // check to land on, so the backend stops it synchronously — polling already halted
      // when status left "running", so it needs restarting here to actually see it.
      if (wasAwaitingReview) setPollGeneration(g => g + 1)
    } catch (err) {
      console.error("Failed to stop task:", err)
      setIsStopping(false)
    }
  }

  const handlePause = async () => {
    if (isPausing) return
    setIsPausing(true)
    try {
      await pauseTask(activeTaskId)
      // Same cooperative-interrupt timing caveat as Stop — the 2s poll picks up
      // status:"paused" once it actually takes effect.
    } catch (err) {
      console.error("Failed to pause task:", err)
      setIsPausing(false)
    }
  }

  const handleResume = async () => {
    if (isResuming) return
    setIsResuming(true)
    try {
      await resumeTask(activeTaskId)
      setPollGeneration(g => g + 1)  // restart polling — see the effect above
    } catch (err) {
      console.error("Failed to resume task:", err)
      setIsResuming(false)
    }
  }

  const handleRerun = async () => {
    if (isRerunning) return
    setIsRerunning(true)
    try {
      // A failed run's checkpoint may reflect whatever broken intermediate state
      // caused the failure — not safe to resume from. Submitting fresh (same query/
      // type/settings, new task_id) is the same pattern EmptyState/doFollowUp already
      // use, and guarantees a clean start rather than replaying a known-bad state.
      const res = await submitTask(activeQuery, "", activeTaskType, activeTaskType === "report" && requireHumanReview)
      setActiveTaskId(res.data.task_id)
      setTask(null)
    } catch (err) {
      console.error("Failed to rerun task:", err)
    } finally {
      setIsRerunning(false)
    }
  }

  const handleReviewDecision = async (decision) => {
    if (isReviewSubmitting) return
    setIsReviewSubmitting(true)
    try {
      await submitReviewDecision(activeTaskId, decision)
      setPollGeneration(g => g + 1)  // restart polling — see the effect above
    } catch (err) {
      console.error("Failed to submit review decision:", err)
      setIsReviewSubmitting(false)
    }
  }

  const doFollowUp = async (text, type) => {
    try {
      // Follow-ups reuse the same require_human_review choice made at initial
      // submission rather than exposing a second toggle in the follow-up bar — a
      // follow-up is a new task under the hood, but re-asking on every one is friction
      // nobody asked for.
      const res = await submitTask(text, "", type, type === "report" && requireHumanReview)
      setActiveTaskId(res.data.task_id); setActiveQuery(text); setActiveTaskType(type); setTask(null)
    } catch (err) { console.error(err) }
  }

  const handleFollowUp = async (text, mode) => {
    if (!text.trim() || isCheckingClarity) return
    const type = mode || activeTaskType
    setIsCheckingClarity(true)
    try {
      const res = await clarifyTask(text, type)
      const questions = res.data.questions || []
      if (questions.length > 0) {
        setClarifyState({ text, type, questions })
        setIsCheckingClarity(false)
        return
      }
    } catch (err) {
      console.error("clarify_task failed, proceeding without it:", err)
    }
    setIsCheckingClarity(false)
    doFollowUp(text, type)
  }

  const handleClarifyConfirm = (resolvedAnswers) => {
    const { text, type } = clarifyState
    setClarifyState(null)
    doFollowUp(appendClarificationContext(text, resolvedAnswers), type)
  }

  const handleClarifySkip = () => {
    const { text, type } = clarifyState
    setClarifyState(null)
    doFollowUp(text, type)
  }

  const isRunning        = task?.status === "running"
  const isComplete       = task?.status === "completed"
  const isFailed         = task?.status === "failed"
  const isStopped        = task?.status === "stopped"
  const isPaused         = task?.status === "paused"
  const isAwaitingReview = task?.status === "awaiting_review"
  const isReport         = activeTaskType === "report"

  const headerTitle = isFailed ? "Analysis Failed"
    : isStopped ? "Analysis Stopped"
    : isPaused ? "Analysis Paused"
    : isAwaitingReview ? "Awaiting Your Review"
    : isComplete ? (isReport ? "Research Report" : "Analysis Result")
    : (isReport ? "Report Mode" : "Analysis In Progress")

  const modeLabel = isReport ? brand.modeLabels.report : brand.modeLabels.qa
  const meta = statusMeta(task?.status)
  const statusLabel = meta.label
  // "Running" gets one extra distinction STATUS_META doesn't carry (it's task_type-, not
  // status-, driven): report mode shows purple while it runs, qa mode shows the shared blue.
  const badgeColor = isRunning && isReport ? "bg-purple-50 text-purple-600 border-purple-200" : meta.badge

  return (
    <div className="h-screen flex bg-background overflow-hidden font-sans">

      {/* Permanent sidebar (desktop) */}
      <div className="hidden md:flex w-64 shrink-0 border-r border-border flex-col bg-sidebar">
        <Sidebar onNew={onNew} currentTaskId={activeTaskId} onSelect={handleSelect} onDomainPacks={onDomainPacks} onData={onData} />
      </div>

      {/* Main column */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">

        {/* TOP BAR */}
        <div className="h-14 border-b border-border bg-card flex items-center justify-between px-4 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="md:hidden shrink-0">
                  <Menu className="w-4 h-4" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-64 p-0 border-r border-border bg-sidebar" showCloseButton={false}>
                <SheetTitle className="sr-only">Navigation</SheetTitle>
                <Sidebar onNew={() => { onNew(); setDrawerOpen(false) }} currentTaskId={activeTaskId} onSelect={handleSelect} onDomainPacks={() => { onDomainPacks(); setDrawerOpen(false) }} onData={() => { onData(); setDrawerOpen(false) }} />
              </SheetContent>
            </Sheet>

            <h1 className="text-heading text-foreground leading-none shrink-0">{headerTitle}</h1>
            <Badge variant="outline" className={`gap-1.5 text-caption shrink-0 ${badgeColor}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${isRunning ? "animate-pulse" : ""}`} style={{ backgroundColor: "currentColor" }} />
              {modeLabel} · {statusLabel}
            </Badge>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {isRunning && (
              <>
                <Button
                  size="sm" variant="outline" onClick={handlePause} disabled={isPausing}
                  title={isPausing ? "Pausing — takes effect at the next safe point" : "Pause this analysis"}
                  className="h-8 text-body gap-1.5"
                >
                  <Pause className="w-3.5 h-3.5" /> {isPausing ? "Pausing…" : "Pause"}
                </Button>
                <Button
                  size="sm" variant="outline" onClick={handleStop} disabled={isStopping}
                  title={isStopping ? "Stopping — takes effect at the next safe point" : "Stop this analysis"}
                  className="h-8 text-body gap-1.5 text-destructive border-destructive/30"
                >
                  <Square className="w-3.5 h-3.5" /> {isStopping ? "Stopping…" : "Stop"}
                </Button>
              </>
            )}
            {isPaused && (
              <Button
                size="sm" variant="outline" onClick={handleResume} disabled={isResuming}
                title="Resume this analysis — the step that was interrupted restarts from scratch"
                className="h-8 text-body gap-1.5 text-amber-600 border-amber-200"
              >
                <Play className="w-3.5 h-3.5" /> {isResuming ? "Resuming…" : "Resume"}
              </Button>
            )}
            {isAwaitingReview && (
              // Refine/Finalize live on the review card itself, below — this is just an
              // escape hatch for a reviewer who never responds (mirrors Stop's cooperative
              // mechanism, but the task isn't inside graph.invoke() right now, so the
              // backend stops it directly instead of waiting for a node boundary).
              <Button
                size="sm" variant="outline" onClick={handleStop} disabled={isStopping}
                title="Stop this analysis without waiting for a review decision"
                className="h-8 text-body gap-1.5 text-destructive border-destructive/30"
              >
                <Square className="w-3.5 h-3.5" /> {isStopping ? "Stopping…" : "Stop"}
              </Button>
            )}
            {isFailed && (
              <Button
                size="sm" variant="outline" onClick={handleRerun} disabled={isRerunning}
                title="Submit this same query again as a new analysis"
                className="h-8 text-body gap-1.5"
              >
                <RotateCcw className="w-3.5 h-3.5" /> {isRerunning ? "Rerunning…" : "Rerun"}
              </Button>
            )}
            {/* Export controls live inline with the result (CSV in ReportSections,
                print-to-PDF in ReportView) rather than duplicated here. */}
          </div>
        </div>

        {/* CONTENT */}
        <div className="flex-1 overflow-y-auto bg-background">
          <div className="max-w-7xl mx-auto px-6 py-6">
            <ReportPanel
              task={task} query={activeQuery} onFollowUp={handleFollowUp} isFollowUpBusy={isCheckingClarity}
              onReviewDecision={handleReviewDecision} isReviewSubmitting={isReviewSubmitting}
            />
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
