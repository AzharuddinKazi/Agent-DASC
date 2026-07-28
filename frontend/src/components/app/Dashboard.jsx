import { useState, useEffect } from "react"
import { getTask, submitTask } from "../../api"
import { brand } from "../../config/brand"
import Sidebar from "./Sidebar"
import ReportPanel from "./ReportPanel"
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Menu, Pause, Square } from "lucide-react"

export default function Dashboard({ query, taskId, taskType: initialTaskType, onNew, onDomainPacks }) {
  const [task, setTask]                 = useState(null)
  const [activeQuery, setActiveQuery]   = useState(query)
  const [activeTaskId, setActiveTaskId] = useState(taskId)
  const [activeTaskType, setActiveTaskType] = useState(initialTaskType || "qa")
  const [drawerOpen, setDrawerOpen]     = useState(false)

  useEffect(() => {
    if (!activeTaskId) return
    setTask(null)
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
  }, [activeTaskId])

  const handleSelect = (id, q, type) => { setActiveTaskId(id); setActiveQuery(q); if (type) setActiveTaskType(type); setDrawerOpen(false) }
  const handleFollowUp = async (text, mode) => {
    if (!text.trim()) return
    const type = mode || activeTaskType
    try {
      const res = await submitTask(text, "", type)
      setActiveTaskId(res.data.task_id); setActiveQuery(text); setActiveTaskType(type); setTask(null)
    } catch (err) { console.error(err) }
  }

  const isRunning  = task?.status === "running"
  const isComplete = task?.status === "completed"
  const isFailed   = task?.status === "failed"
  const isReport   = activeTaskType === "report"

  const headerTitle = isFailed ? "Analysis Failed"
    : isComplete ? (isReport ? "Research Report" : "Analysis Result")
    : (isReport ? "Report Mode" : "Analysis In Progress")

  const modeLabel = isReport ? brand.modeLabels.report : brand.modeLabels.qa
  const statusLabel = isFailed ? "Failed" : isComplete ? "Complete" : "Running"
  const badgeColor = isFailed ? "bg-danger/10 text-danger border-danger/30"
    : isComplete ? "bg-success/10 text-success border-success/30"
    : isReport ? "bg-purple-50 text-purple-600 border-purple-200"
    : "bg-blue-50 text-blue-600 border-blue-200"

  return (
    <div className="h-screen flex bg-background overflow-hidden font-sans">

      {/* Permanent sidebar (desktop) */}
      <div className="hidden md:flex w-60 shrink-0 border-r border-border flex-col bg-sidebar">
        <Sidebar onNew={onNew} currentTaskId={activeTaskId} onSelect={handleSelect} onDomainPacks={onDomainPacks} />
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
              <SheetContent side="left" className="w-60 p-0 border-r border-border bg-sidebar" showCloseButton={false}>
                <SheetTitle className="sr-only">Navigation</SheetTitle>
                <Sidebar onNew={() => { onNew(); setDrawerOpen(false) }} currentTaskId={activeTaskId} onSelect={handleSelect} onDomainPacks={() => { onDomainPacks(); setDrawerOpen(false) }} />
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
                <Button size="sm" variant="outline" disabled title="Not yet available" className="h-8 text-body gap-1.5">
                  <Pause className="w-3.5 h-3.5" /> Pause
                </Button>
                <Button size="sm" variant="outline" disabled title="Not yet available" className="h-8 text-body gap-1.5 text-destructive border-destructive/30">
                  <Square className="w-3.5 h-3.5" /> Stop
                </Button>
              </>
            )}
            {/* Export controls live inline with the result (CSV in ReportSections,
                print-to-PDF in ReportView) rather than duplicated here. */}
          </div>
        </div>

        {/* CONTENT */}
        <div className="flex-1 overflow-y-auto bg-background">
          <div className="max-w-7xl mx-auto px-6 py-6">
            <ReportPanel task={task} query={activeQuery} onFollowUp={handleFollowUp} />
          </div>
        </div>
      </div>
    </div>
  )
}
