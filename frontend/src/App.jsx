import { useState } from "react"
import EmptyState from "./components/app/EmptyState"
import Dashboard from "./components/app/Dashboard"
import DomainPacks from "./components/app/DomainPacks"
import DataBrowser from "./components/app/DataBrowser"
import Login from "./components/app/Login"
import { TooltipProvider } from "./components/ui/tooltip"
import { useAuth } from "./hooks/useAuth"

function Spinner() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-subtle">
      <div className="w-6 h-6 border-2 border-muted-foreground/30 border-t-foreground rounded-full animate-spin" />
    </div>
  )
}

export default function App() {
  const { user, loading, refresh } = useAuth()
  const [view, setView]         = useState("empty")
  const [query, setQuery]       = useState("")
  const [taskId, setTaskId]     = useState(null)
  const [taskType, setTaskType] = useState("qa")
  const [requireHumanReview, setRequireHumanReview] = useState(false)

  const handleSubmit = (q, id, type = "qa", reviewFlag = false) => {
    setQuery(q)
    setTaskId(id)
    setTaskType(type)
    setRequireHumanReview(reviewFlag)
    setView("dashboard")
  }

  const handleNew = () => {
    setView("empty")
    setQuery("")
    setTaskId(null)
  }

  const handleDomainPacks = () => setView("domainPacks")
  const handleData = () => setView("data")

  if (loading) return <Spinner />
  if (!user) return <Login onSignedIn={refresh} />

  return (
    <TooltipProvider>
      <div className="min-h-screen bg-surface-subtle text-slate-900">
        {view === "empty" && <EmptyState onSubmit={handleSubmit} onDomainPacks={handleDomainPacks} onData={handleData} />}
        {view === "dashboard" && (
          <Dashboard query={query} taskId={taskId} taskType={taskType} requireHumanReview={requireHumanReview} onNew={handleNew} onDomainPacks={handleDomainPacks} onData={handleData} />
        )}
        {view === "domainPacks" && (
          <DomainPacks onNew={handleNew} onSelect={handleSubmit} onData={handleData} />
        )}
        {view === "data" && (
          <DataBrowser onNew={handleNew} onSelect={handleSubmit} onDomainPacks={handleDomainPacks} />
        )}
      </div>
    </TooltipProvider>
  )
}
