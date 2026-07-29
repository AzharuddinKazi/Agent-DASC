import { useState } from "react"
import EmptyState from "./components/app/EmptyState"
import Dashboard from "./components/app/Dashboard"
import DomainPacks from "./components/app/DomainPacks"
import Login from "./components/app/Login"
import { TooltipProvider } from "./components/ui/tooltip"
import { useAuth } from "./hooks/useAuth"

export default function App() {
  const { user, loading } = useAuth()
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

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center bg-background">
        <div className="w-6 h-6 border-2 border-muted-foreground/30 border-t-foreground rounded-full animate-spin" />
      </div>
    )
  }

  if (!user) {
    return <Login />
  }

  return (
    <TooltipProvider>
      <div className="min-h-screen bg-surface-subtle text-slate-900">
        {view === "empty" && <EmptyState onSubmit={handleSubmit} onDomainPacks={handleDomainPacks} />}
        {view === "dashboard" && (
          <Dashboard query={query} taskId={taskId} taskType={taskType} requireHumanReview={requireHumanReview} onNew={handleNew} onDomainPacks={handleDomainPacks} />
        )}
        {view === "domainPacks" && (
          <DomainPacks onNew={handleNew} onSelect={handleSubmit} />
        )}
      </div>
    </TooltipProvider>
  )
}
