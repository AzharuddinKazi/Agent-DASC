import { useEffect, useState } from "react"
import { getTask, submitTask } from "@/api"
import Sidebar from "./Sidebar"
import QueryPanel from "./QueryPanel"
import ReportPanel from "./ReportPanel"

export default function Dashboard({ query, taskId, onNew }) {
  const [task, setTask]             = useState(null)
  const [activeQuery, setActiveQuery] = useState(query)
  const [activeTaskId, setActiveTaskId] = useState(taskId)

  useEffect(() => {
    if (!activeTaskId) return
    setTask(null)

    const poll = async () => {
      try {
        const r = await getTask(activeTaskId)
        setTask(r.data)
        if (r.data.status !== "running") clearInterval(interval)
      } catch {}
    }

    poll()
    const interval = setInterval(poll, 2000)
    return () => clearInterval(interval)
  }, [activeTaskId])

  const handleSelect = (id, q) => {
    setActiveTaskId(id)
    setActiveQuery(q)
  }

  const handleNew = () => {
    onNew()
  }

  return (
    <div className="h-screen grid grid-cols-[220px_340px_1fr]">
      <Sidebar
        onNew={handleNew}
        currentTaskId={activeTaskId}
        onSelect={handleSelect}
      />
      <QueryPanel query={activeQuery} task={task} />
      <ReportPanel task={task} query={activeQuery} />
    </div>
  )
}