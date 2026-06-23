import { useState } from "react"
import EmptyState from "./components/app/EmptyState"
import Dashboard from "./components/app/Dashboard"
import { TooltipProvider } from "./components/ui/tooltip"

export default function App() {
  const [view, setView]         = useState("empty")
  const [query, setQuery]       = useState("")
  const [taskId, setTaskId]     = useState(null)
  const [taskType, setTaskType] = useState("qa")

  const handleSubmit = (q, id, type = "qa") => {
    setQuery(q)
    setTaskId(id)
    setTaskType(type)
    setView("dashboard")
  }

  const handleNew = () => {
    setView("empty")
    setQuery("")
    setTaskId(null)
  }

  return (
    <TooltipProvider>
      <div className="min-h-screen bg-surface-subtle text-slate-900">
        {view === "empty" && <EmptyState onSubmit={handleSubmit} />}
        {view === "dashboard" && (
          <Dashboard query={query} taskId={taskId} taskType={taskType} onNew={handleNew} />
        )}
      </div>
    </TooltipProvider>
  )
}