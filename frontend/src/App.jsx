import { useState } from "react"
import EmptyState from "@/components/app/EmptyState"
import Dashboard from "@/components/app/Dashboard"
import { TooltipProvider } from "@/components/ui/tooltip"

export default function App() {
  const [view, setView]       = useState("empty")
  const [query, setQuery]     = useState("")
  const [taskId, setTaskId]   = useState(null)

  const handleSubmit = (q, id) => {
    setQuery(q)
    setTaskId(id)
    setView("dashboard")
  }

  const handleNew = () => {
    setView("empty")
    setQuery("")
    setTaskId(null)
  }

  return (
    <TooltipProvider>
      <div className="min-h-screen bg-[#09090B]">
        {view === "empty" && <EmptyState onSubmit={handleSubmit} />}
        {view === "dashboard" && (
          <Dashboard query={query} taskId={taskId} onNew={handleNew} />
        )}
      </div>
    </TooltipProvider>
  )
}