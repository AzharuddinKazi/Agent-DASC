import { useCallback, useEffect, useState } from "react"
import { getAdminTasks, stopAdminTask, rerunAdminTask, deleteAdminTask } from "../api"
import { statusMeta } from "../lib/taskStatus"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { ListChecks, Square, RotateCcw, Trash2 } from "lucide-react"

function timeAgo(iso) {
  if (!iso) return "—"
  const s = Math.floor((Date.now() - new Date(iso)) / 1000)
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

// Polls the same way Sidebar.jsx's task list does (plain setInterval, no dedicated hook)
// — this is the one place in the admin panel a live-updating table earns its keep, since
// tasks across every user are actively transitioning status while an admin has this open.
export default function AdminTasksPanel() {
  const [tasks, setTasks]     = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState("")
  const [busyId, setBusyId]   = useState(null)
  const [confirmDelete, setConfirmDelete] = useState(null)   // task_id pending delete confirmation

  const load = useCallback(async () => {
    try {
      const r = await getAdminTasks({ limit: 100 })
      setTasks(r.data)
      setError("")
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Failed to load tasks")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [load])

  const withBusy = async (taskId, action) => {
    setBusyId(taskId)
    try { await action() } catch (err) { setError(err?.response?.data?.detail || err?.message || "Action failed") }
    finally { setBusyId(null); load() }
  }

  const handleDelete = async () => {
    const taskId = confirmDelete
    setConfirmDelete(null)
    await withBusy(taskId, () => deleteAdminTask(taskId))
  }

  return (
    <div className="max-w-5xl mx-auto flex flex-col gap-6 w-full">
      <div>
        <div className="flex items-center gap-2 mb-1.5">
          <ListChecks className="w-5 h-5 text-foreground" />
          <h2 className="text-display-sm font-bold text-foreground tracking-tight leading-tight">Tasks</h2>
        </div>
        <p className="text-body text-muted-foreground leading-relaxed max-w-xl">
          Every task across every user — stop a run in progress, rerun a finished one, or
          delete a stale row.
        </p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-heading">All tasks ({tasks.length})</CardTitle>
        </CardHeader>
        <CardContent className="pt-0 overflow-x-auto">
          {loading ? (
            <p className="text-body text-muted-foreground">Loading…</p>
          ) : tasks.length === 0 ? (
            <p className="text-body text-muted-foreground">No tasks yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Query</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>User</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tasks.map(task => {
                  const meta = statusMeta(task.status)
                  const busy = busyId === task.task_id
                  return (
                    <TableRow key={task.task_id}>
                      <TableCell className="max-w-xs truncate" title={task.query}>{task.query}</TableCell>
                      <TableCell className="capitalize">{task.task_type}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className={meta.badge}>{meta.label}</Badge>
                      </TableCell>
                      <TableCell className="text-caption text-muted-foreground">{task.user_id}</TableCell>
                      <TableCell className="text-caption text-muted-foreground">{timeAgo(task.created_at)}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          {task.status === "running" && (
                            <Button
                              variant="ghost" size="icon-sm" disabled={busy} title="Stop"
                              onClick={() => withBusy(task.task_id, () => stopAdminTask(task.task_id))}
                            >
                              <Square className="w-3.5 h-3.5" />
                            </Button>
                          )}
                          <Button
                            variant="ghost" size="icon-sm" disabled={busy} title="Rerun"
                            onClick={() => withBusy(task.task_id, () => rerunAdminTask(task.task_id))}
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
                          </Button>
                          <Button
                            variant="ghost" size="icon-sm" disabled={busy} title="Delete"
                            className="text-destructive"
                            onClick={() => setConfirmDelete(task.task_id)}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={!!confirmDelete} onOpenChange={open => !open && setConfirmDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete this task?</DialogTitle>
          </DialogHeader>
          <p className="text-body text-muted-foreground">
            This permanently removes the task row. This can't be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDelete(null)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDelete}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
