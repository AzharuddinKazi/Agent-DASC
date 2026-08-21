import { useCallback, useEffect, useState } from "react"
import { getAdminDomainPacks, createDomainPack, updateDomainPack, deleteDomainPack } from "../api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Package, Plus, Pencil, Trash2 } from "lucide-react"

const EMPTY_FORM = {
  pack_id: "", name: "", description: "", tags: "", example_question: "",
  report_persona: "", report_classification: "",
}

// pack_id is only editable at creation (it's the row's key) — the form disables it once
// editing an existing pack, matching domain_pack_admin.py's create_pack/update_pack split.
function PackFormDialog({ open, onOpenChange, initial, onSubmit, error }) {
  const [form, setForm] = useState(EMPTY_FORM)
  const isEdit = !!initial

  useEffect(() => {
    setForm(initial ? {
      pack_id: initial.id, name: initial.name || "", description: initial.description || "",
      tags: (initial.tags || []).join(", "), example_question: initial.example_question || "",
      report_persona: initial.report_persona || "", report_classification: initial.report_classification || "",
    } : EMPTY_FORM)
  }, [initial, open])

  const handleSubmit = e => {
    e.preventDefault()
    onSubmit({
      ...form,
      tags: form.tags.split(",").map(t => t.trim()).filter(Boolean),
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit domain pack" : "New domain pack"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pack_id" className="text-xs">Pack ID</Label>
            <Input
              id="pack_id" required disabled={isEdit} value={form.pack_id}
              onChange={e => setForm(f => ({ ...f, pack_id: e.target.value }))}
              placeholder="fraud-aml"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="name" className="text-xs">Name</Label>
            <Input
              id="name" required value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="description" className="text-xs">Description</Label>
            <Textarea
              id="description" rows={2} value={form.description}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="tags" className="text-xs">Tags (comma-separated)</Label>
            <Input
              id="tags" value={form.tags}
              onChange={e => setForm(f => ({ ...f, tags: e.target.value }))}
              placeholder="finance, compliance"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="example_question" className="text-xs">Example question</Label>
            <Input
              id="example_question" value={form.example_question}
              onChange={e => setForm(f => ({ ...f, example_question: e.target.value }))}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="report_persona" className="text-xs">Report persona</Label>
            <Textarea
              id="report_persona" rows={2} value={form.report_persona}
              onChange={e => setForm(f => ({ ...f, report_persona: e.target.value }))}
              placeholder="You are a senior data analyst writing a report for a business stakeholder."
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="report_classification" className="text-xs">Report classification (optional)</Label>
            <Input
              id="report_classification" value={form.report_classification}
              onChange={e => setForm(f => ({ ...f, report_classification: e.target.value }))}
            />
          </div>

          {error && <p className="text-caption text-destructive">{error}</p>}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit">{isEdit ? "Save changes" : "Create pack"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function AdminDomainPacksPanel() {
  const [packs, setPacks]     = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState("")
  const [formError, setFormError] = useState("")
  const [editing, setEditing] = useState(null)     // pack object being edited, or null
  const [dialogOpen, setDialogOpen] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(null)   // pack id pending delete

  const load = useCallback(async () => {
    try {
      const r = await getAdminDomainPacks()
      setPacks(r.data)
      setError("")
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Failed to load domain packs")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const openCreate = () => { setEditing(null); setFormError(""); setDialogOpen(true) }
  const openEdit = pack => { setEditing(pack); setFormError(""); setDialogOpen(true) }

  const handleSubmit = async data => {
    try {
      if (editing) {
        const { pack_id, ...updates } = data
        await updateDomainPack(pack_id, updates)
      } else {
        await createDomainPack(data)
      }
      setDialogOpen(false)
      load()
    } catch (err) {
      setFormError(err?.response?.data?.detail || err?.message || "Failed to save pack")
    }
  }

  const handleDelete = async () => {
    const id = confirmDelete
    setConfirmDelete(null)
    try { await deleteDomainPack(id) } catch (err) { setError(err?.response?.data?.detail || err?.message || "Failed to delete pack") }
    load()
  }

  return (
    <div className="max-w-4xl mx-auto flex flex-col gap-6 w-full">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <Package className="w-5 h-5 text-foreground" />
            <h2 className="text-display-sm font-bold text-foreground tracking-tight leading-tight">Domain packs</h2>
          </div>
          <p className="text-body text-muted-foreground leading-relaxed max-w-xl">
            Create, edit, or remove the packs available on the Domain Packs page.
          </p>
        </div>
        <Button size="sm" onClick={openCreate}>
          <Plus className="w-3.5 h-3.5" /> New pack
        </Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading ? (
        <p className="text-body text-muted-foreground">Loading…</p>
      ) : packs.length === 0 ? (
        <p className="text-body text-muted-foreground">No domain packs yet.</p>
      ) : (
        <div className="flex flex-col gap-3">
          {packs.map(pack => (
            <Card key={pack.id}>
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center shrink-0">
                      <Package className="w-4 h-4 text-foreground" />
                    </div>
                    <CardTitle className="text-heading flex items-center gap-2">
                      {pack.name}
                      {pack.active && <Badge variant="outline" className="bg-success/10 text-success border-success/30">Active</Badge>}
                    </CardTitle>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <Button variant="ghost" size="icon-sm" title="Edit" onClick={() => openEdit(pack)}>
                      <Pencil className="w-3.5 h-3.5" />
                    </Button>
                    <Button
                      variant="ghost" size="icon-sm" title="Delete" className="text-destructive"
                      onClick={() => setConfirmDelete(pack.id)}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-0 flex flex-col gap-2">
                <p className="text-body text-muted-foreground leading-relaxed">{pack.description}</p>
                {pack.tags?.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {pack.tags.map(tag => <Badge key={tag} variant="outline">{tag}</Badge>)}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <PackFormDialog
        open={dialogOpen} onOpenChange={setDialogOpen} initial={editing}
        onSubmit={handleSubmit} error={formError}
      />

      <Dialog open={!!confirmDelete} onOpenChange={open => !open && setConfirmDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete this domain pack?</DialogTitle>
          </DialogHeader>
          <p className="text-body text-muted-foreground">
            Deactivates it globally if currently active, and permanently removes its catalog
            row. This can't be undone.
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
