import { useCallback, useEffect, useRef, useState } from "react"
import { getDomainPacks, getDomainPackConfig, domainPackDownloadUrl, activateDomainPack, deactivateDomainPack, getPackDocuments, uploadPackDocument, deletePackDocument } from "../../api"
import Sidebar from "./Sidebar"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from "@/components/ui/sheet"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { Menu, Package, Download, Upload, FileText, X, CheckCircle2, Power, Database, UserCog, Clock, Layers, MessageSquareText } from "lucide-react"

const STATUS_STYLE = {
  processing: "bg-info/10 text-info border-info/30",
  ready:      "bg-success/10 text-success border-success/20",
  failed:     "bg-destructive/10 text-destructive border-destructive/30",
}

function timeAgo(iso) {
  if (!iso) return null
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

// Shared across the stats strip and the document list below it so they poll from a
// single source of truth instead of each firing their own request every 3s.
function usePackDocuments(packId) {
  const [docs, setDocs]       = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError]     = useState("")

  const load = useCallback(async () => {
    if (!packId) return
    try { const r = await getPackDocuments(packId); setDocs(r.data) }
    catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [packId])

  useEffect(() => {
    if (!packId) return
    load()
    const t = setInterval(load, 3000)
    return () => clearInterval(t)
  }, [packId, load])

  const upload = async file => {
    setUploading(true)
    setError("")
    try {
      await uploadPackDocument(packId, file)
      await load()
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Upload failed")
    } finally {
      setUploading(false)
    }
  }

  const remove = async docId => {
    setDocs(d => d.filter(doc => doc.id !== docId))
    try { await deletePackDocument(packId, docId) } catch (e) { console.error(e) }
  }

  return { docs, loading, uploading, error, upload, remove }
}

function PackStats({ docs, loading }) {
  if (loading) return null

  const lastAdded = timeAgo(docs[0]?.created_at)   // API orders by created_at desc

  return (
    <div className="grid grid-cols-2 gap-px rounded-lg border border-border bg-border overflow-hidden mb-4">
      <div className="bg-card px-3 py-2">
        <p className="text-body font-bold text-foreground tabular-nums">{docs.length}</p>
        <p className="text-label text-muted-foreground">documents indexed</p>
      </div>
      <div className="bg-card px-3 py-2">
        <p className="text-body font-bold text-foreground flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5 text-muted-foreground" />
          {lastAdded || "—"}
        </p>
        <p className="text-label text-muted-foreground">last document added</p>
      </div>
    </div>
  )
}

function KnowledgeBase({ active, docs, loading, uploading, error, onUpload, onDelete }) {
  const fileInputRef = useRef(null)

  const handleFile = e => {
    const file = e.target.files?.[0]
    if (file) onUpload(file)
    e.target.value = ""
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <p className="text-label font-semibold uppercase tracking-widest text-muted-foreground">
          Knowledge base
        </p>
        <Button
          size="sm" variant="outline" className="h-6 gap-1 text-label px-2"
          disabled={uploading}
          onClick={() => fileInputRef.current?.click()}
        >
          <Upload className="w-3 h-3" />
          {uploading ? "Uploading…" : "Add document"}
        </Button>
        <input
          ref={fileInputRef} type="file" className="hidden"
          accept=".pdf,.docx,.txt,.md"
          onChange={handleFile}
        />
      </div>

      {error && <p className="text-label text-destructive">{error}</p>}

      {!active && (
        <p className="text-label text-amber-600 bg-amber-50 border border-amber-200 rounded-md px-2 py-1.5">
          This pack isn't active yet — documents upload and index fine, but only the
          active pack's knowledge base feeds the Planner. Activate it above to switch to it.
        </p>
      )}

      {!loading && docs.length === 0 && (
        <p className="text-label text-muted-foreground/70">
          No reference documents yet — PDFs, Word docs, or text/markdown files feed the
          Planner as subject-matter context.
        </p>
      )}

      <div className="flex flex-col gap-1">
        {docs.map(doc => (
          <div key={doc.id} className="flex items-center gap-2 px-2 py-1.5 rounded-md bg-muted/40">
            <FileText className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
            <span className="text-caption text-foreground truncate flex-1" title={doc.filename}>{doc.filename}</span>
            <Badge variant="outline" className={`text-label font-bold shrink-0 ${STATUS_STYLE[doc.status] || ""}`}>
              {doc.status === "ready" ? `${doc.chunk_count} chunks` : doc.status}
            </Badge>
            <button onClick={() => onDelete(doc.id)} className="text-muted-foreground hover:text-destructive shrink-0 cursor-pointer">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

function PackCustomization({ packId }) {
  const [config, setConfig]   = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try { const r = await getDomainPackConfig(packId); setConfig(r.data) }
    catch { setConfig(null) }
    finally { setLoading(false) }
  }, [packId])

  useEffect(() => { load() }, [load])

  if (loading) return <p className="text-caption text-muted-foreground">Loading…</p>
  if (!config) return null

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-start gap-2">
        <UserCog className="w-4 h-4 text-muted-foreground shrink-0 mt-0.5" />
        <div>
          <p className="text-label font-semibold uppercase tracking-widest text-muted-foreground mb-0.5">
            Report persona
          </p>
          <p className="text-caption text-foreground italic">"{config.report_persona}"</p>
        </div>
      </div>

      {config.report_classification && (
        <div>
          <p className="text-label font-semibold uppercase tracking-widest text-muted-foreground mb-1">
            Report classification
          </p>
          <Badge variant="outline" className="text-label font-medium">{config.report_classification}</Badge>
        </div>
      )}
    </div>
  )
}

function PackDetailModal({ pack, onClose, onToggleActive, togglingId }) {
  const docsState = usePackDocuments(pack?.id)

  if (!pack) return null

  return (
    <Dialog open={!!pack} onOpenChange={open => !open && onClose()}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center justify-between pr-8 mb-1">
            <div className="w-9 h-9 rounded-lg bg-accent flex items-center justify-center">
              <Package className="w-4.5 h-4.5 text-foreground" />
            </div>
            {pack.active && (
              <Badge className="gap-1 text-label font-bold bg-success/10 text-success border-success/20">
                <CheckCircle2 className="w-3 h-3" />
                Active
              </Badge>
            )}
          </div>
          <DialogTitle>{pack.name}</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-5">
          <PackStats docs={docsState.docs} loading={docsState.loading} />

          <p className="text-body text-muted-foreground leading-relaxed">{pack.description}</p>

          <div className="flex flex-wrap gap-1.5">
            {pack.tags?.map(tag => (
              <Badge key={tag} variant="outline" className="text-label font-medium">{tag}</Badge>
            ))}
          </div>

          <div className="flex items-center gap-2 text-caption text-muted-foreground">
            <Database className="w-3.5 h-3.5 shrink-0" />
            {pack.has_dataset_generator
              ? "Includes an example synthetic dataset generator"
              : "Grounded in real reference data — no synthetic generator"}
          </div>

          <div className="flex flex-wrap items-center gap-2 text-caption text-muted-foreground bg-muted/40 rounded-md px-2.5 py-2">
            <Layers className="w-3.5 h-3.5 shrink-0" />
            <span>Grounds these pipeline stages{pack.active ? "" : " when active"}:</span>
            {["Planner", "Coder", "Verifier"].map(stage => (
              <Badge key={stage} variant="outline" className="text-label font-bold">{stage}</Badge>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <Button
              size="sm" className="gap-1.5"
              variant={pack.active ? "outline" : "default"}
              disabled={togglingId === pack.id}
              onClick={() => onToggleActive(pack)}
            >
              <Power className="w-3.5 h-3.5" />
              {togglingId === pack.id ? "Working…" : pack.active ? "Deactivate" : "Activate"}
            </Button>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button asChild size="icon-sm" variant="ghost" className="text-muted-foreground">
                  <a href={domainPackDownloadUrl(pack.id)} download>
                    <Download className="w-3.5 h-3.5" />
                  </a>
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">Export config as .zip</TooltipContent>
            </Tooltip>
          </div>

          <div className="border-t border-border pt-4">
            <KnowledgeBase
              active={pack.active}
              docs={docsState.docs}
              loading={docsState.loading}
              uploading={docsState.uploading}
              error={docsState.error}
              onUpload={docsState.upload}
              onDelete={docsState.remove}
            />
          </div>

          {pack.example_question && (
            <div className="flex items-start gap-2 text-caption text-muted-foreground">
              <MessageSquareText className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              <span>Try asking — <span className="italic text-foreground">"{pack.example_question}"</span></span>
            </div>
          )}

          <div className="border-t border-border pt-4">
            <PackCustomization packId={pack.id} />
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default function DomainPacks({ onNew, onSelect }) {
  const [packs, setPacks]     = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState("")
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [togglingId, setTogglingId] = useState(null)
  const [selectedPackId, setSelectedPackId] = useState(null)

  const loadPacks = useCallback(async () => {
    try { const r = await getDomainPacks(); setPacks(r.data) }
    catch (err) {
      if (err?.response?.status === 403) {
        setError("Domain packs are currently disabled by an admin.")
      } else {
        setError(err?.message || "Failed to load domain packs — is the backend running?")
      }
    }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { loadPacks() }, [loadPacks])

  const handleToggleActive = async pack => {
    setTogglingId(pack.id)
    try {
      await (pack.active ? deactivateDomainPack() : activateDomainPack(pack.id))
      await loadPacks()
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Failed to update activation")
    } finally {
      setTogglingId(null)
    }
  }

  // Re-derived from the freshly-loaded `packs` array each render (rather than storing the
  // pack object itself in state) so the modal's "Active" badge and buttons stay in sync
  // after activate/deactivate triggers a reload, instead of showing a stale snapshot.
  const selectedPack = packs.find(p => p.id === selectedPackId) || null

  return (
    <div className="h-screen flex bg-background overflow-hidden font-sans">

      {/* Permanent sidebar (desktop) */}
      <div className="hidden md:flex w-64 shrink-0 border-r border-border flex-col bg-sidebar">
        <Sidebar onNew={onNew} currentTaskId={null} onSelect={onSelect} onDomainPacks={() => {}} activeView="domainPacks" />
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
                <Sidebar onNew={() => setDrawerOpen(false)} currentTaskId={null} onSelect={onSelect} onDomainPacks={() => setDrawerOpen(false)} activeView="domainPacks" />
              </SheetContent>
            </Sheet>
            <h1 className="text-heading text-foreground leading-none">Domain Packs</h1>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-8">
          <div className="max-w-4xl mx-auto flex flex-col gap-6">

            <div>
              <h2 className="text-display-sm font-bold text-foreground tracking-tight leading-tight mb-1.5">
                Browse domain packs
              </h2>
              <p className="text-body text-muted-foreground leading-relaxed max-w-2xl">
                Domain packs configure this app's analysis prompts and risk dimensions for a specific
                industry, and include a matching example dataset generator. Click a pack for details,
                its knowledge base, and to activate it.
              </p>
            </div>

            {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
            {error && <p className="text-sm text-destructive">{error}</p>}

            {!loading && !error && packs.length === 0 && (
              <p className="text-sm text-muted-foreground">No domain packs available yet.</p>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {packs.map(pack => (
                <Card
                  key={pack.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelectedPackId(pack.id)}
                  onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelectedPackId(pack.id) } }}
                  className="flex flex-col cursor-pointer hover:border-foreground/30 hover:shadow-sm transition-all"
                >
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between mb-2">
                      <div className="w-9 h-9 rounded-lg bg-accent flex items-center justify-center">
                        <Package className="w-4.5 h-4.5 text-foreground" />
                      </div>
                      {pack.active && (
                        <Badge className="gap-1 text-label font-bold bg-success/10 text-success border-success/20">
                          <CheckCircle2 className="w-3 h-3" />
                          Active
                        </Badge>
                      )}
                    </div>
                    <CardTitle className="text-heading">{pack.name}</CardTitle>
                  </CardHeader>
                  <CardContent className="pt-0 flex flex-col gap-3 flex-1">
                    <p className="text-body text-muted-foreground leading-relaxed line-clamp-3 flex-1">
                      {pack.description}
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {pack.tags?.map(tag => (
                        <Badge key={tag} variant="outline" className="text-label font-medium">{tag}</Badge>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </div>
      </div>

      <PackDetailModal
        pack={selectedPack}
        onClose={() => setSelectedPackId(null)}
        onToggleActive={handleToggleActive}
        togglingId={togglingId}
      />
    </div>
  )
}
