import { useCallback, useEffect, useRef, useState } from "react"
import { getDomainPacks, domainPackDownloadUrl, activateDomainPack, deactivateDomainPack, getPackDocuments, uploadPackDocument, deletePackDocument } from "../../api"
import Sidebar from "./Sidebar"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from "@/components/ui/sheet"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { Menu, Package, Download, Upload, FileText, X, CheckCircle2, Power } from "lucide-react"

const STATUS_STYLE = {
  processing: "bg-info/10 text-info border-info/30",
  ready:      "bg-success/10 text-success border-success/20",
  failed:     "bg-destructive/10 text-destructive border-destructive/30",
}

function KnowledgeBase({ packId, active }) {
  const [docs, setDocs]       = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError]     = useState("")
  const fileInputRef = useRef(null)

  const load = useCallback(async () => {
    try { const r = await getPackDocuments(packId); setDocs(r.data) }
    catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [packId])

  useEffect(() => {
    load()
    const t = setInterval(load, 3000)
    return () => clearInterval(t)
  }, [load])

  const handleFile = async e => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setError("")
    try {
      await uploadPackDocument(packId, file)
      await load()
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Upload failed")
    } finally {
      setUploading(false)
      e.target.value = ""
    }
  }

  const handleDelete = async docId => {
    setDocs(d => d.filter(doc => doc.id !== docId))
    try { await deletePackDocument(packId, docId) } catch (e) { console.error(e) }
  }

  return (
    <div className="border-t border-border pt-3 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <p className="text-[10.5px] font-semibold uppercase tracking-widest text-muted-foreground">
          Knowledge base
        </p>
        <Button
          size="sm" variant="outline" className="h-6 gap-1 text-[11px] px-2"
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

      {error && <p className="text-[11px] text-destructive">{error}</p>}

      {!active && (
        <p className="text-[11px] text-amber-600 bg-amber-50 border border-amber-200 rounded-md px-2 py-1.5">
          This pack isn't active yet — documents upload and index fine, but only the
          active pack's knowledge base feeds the Planner. Click Activate above to switch to it.
        </p>
      )}

      {!loading && docs.length === 0 && (
        <p className="text-[11.5px] text-muted-foreground/70">
          No reference documents yet — PDFs, Word docs, or text/markdown files feed the
          Planner as subject-matter context.
        </p>
      )}

      <div className="flex flex-col gap-1">
        {docs.map(doc => (
          <div key={doc.id} className="flex items-center gap-2 px-2 py-1.5 rounded-md bg-muted/40">
            <FileText className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
            <span className="text-[12px] text-foreground truncate flex-1" title={doc.filename}>{doc.filename}</span>
            <Badge variant="outline" className={`text-[9.5px] font-bold shrink-0 ${STATUS_STYLE[doc.status] || ""}`}>
              {doc.status === "ready" ? `${doc.chunk_count} chunks` : doc.status}
            </Badge>
            <button onClick={() => handleDelete(doc.id)} className="text-muted-foreground hover:text-destructive shrink-0 cursor-pointer">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function DomainPacks({ onNew, onSelect }) {
  const [packs, setPacks]     = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState("")
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [togglingId, setTogglingId] = useState(null)

  const loadPacks = useCallback(async () => {
    try { const r = await getDomainPacks(); setPacks(r.data) }
    catch (err) { setError(err?.message || "Failed to load domain packs — is the backend running?") }
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

  return (
    <div className="h-screen flex bg-background overflow-hidden font-sans">

      {/* Permanent sidebar (desktop) */}
      <div className="hidden md:flex w-[240px] shrink-0 border-r border-border flex-col bg-sidebar">
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
              <SheetContent side="left" className="w-[240px] p-0 border-r border-border bg-sidebar" showCloseButton={false}>
                <SheetTitle className="sr-only">Navigation</SheetTitle>
                <Sidebar onNew={() => setDrawerOpen(false)} currentTaskId={null} onSelect={onSelect} onDomainPacks={() => setDrawerOpen(false)} activeView="domainPacks" />
              </SheetContent>
            </Sheet>
            <h1 className="text-[15px] font-bold text-foreground leading-none">Domain Packs</h1>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-8">
          <div className="max-w-4xl mx-auto flex flex-col gap-6">

            <div>
              <h2 className="text-[1.5rem] font-bold text-foreground tracking-tight leading-tight mb-1.5">
                Browse domain packs
              </h2>
              <p className="text-[14px] text-muted-foreground leading-relaxed max-w-2xl">
                Domain packs configure this app's analysis prompts and risk dimensions for a specific
                industry, and include a matching example dataset generator. Their knowledge base feeds
                the Planner subject-matter context — add reference documents below.
              </p>
            </div>

            {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
            {error && <p className="text-sm text-destructive">{error}</p>}

            {!loading && !error && packs.length === 0 && (
              <p className="text-sm text-muted-foreground">No domain packs available yet.</p>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {packs.map(pack => (
                <Card key={pack.id} className="flex flex-col">
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between mb-2">
                      <div className="w-9 h-9 rounded-lg bg-accent flex items-center justify-center">
                        <Package className="w-4.5 h-4.5 text-foreground" />
                      </div>
                      {pack.active && (
                        <Badge className="gap-1 text-[10px] font-bold bg-success/10 text-success border-success/20">
                          <CheckCircle2 className="w-3 h-3" />
                          Active
                        </Badge>
                      )}
                    </div>
                    <CardTitle className="text-[15px] font-bold">{pack.name}</CardTitle>
                  </CardHeader>
                  <CardContent className="pt-0 flex flex-col gap-4 flex-1">
                    <p className="text-[13px] text-muted-foreground leading-relaxed flex-1">
                      {pack.description}
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {pack.tags?.map(tag => (
                        <Badge key={tag} variant="outline" className="text-[10px] font-medium">{tag}</Badge>
                      ))}
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        size="sm" className="gap-1.5"
                        variant={pack.active ? "outline" : "default"}
                        disabled={togglingId === pack.id}
                        onClick={() => handleToggleActive(pack)}
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

                    <KnowledgeBase packId={pack.id} active={pack.active} />
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
