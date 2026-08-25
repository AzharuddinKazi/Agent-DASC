import { useCallback, useEffect, useState } from "react"
import { getDemoDataFiles, getDemoDocuments } from "../../api"
import Sidebar from "./Sidebar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from "@/components/ui/sheet"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import { Menu, Database, FileText } from "lucide-react"

const STATUS_STYLE = {
  ready:      "bg-success/10 text-success border-success/30",
  processing: "bg-blue-100 text-blue-700 border-blue-200",
  failed:     "bg-danger/10 text-danger border-danger/30",
}

function formatBytes(n) {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

// Read-only, every-signed-in-user view of what data this deployment already has loaded —
// same underlying listing as the admin Data panel (see AdminDataPanel.jsx), just gated by
// the demo_mode feature flag instead of admin status. Only reachable while an admin has
// demo_mode on (see Sidebar's nav link); the backend 403s these endpoints otherwise, so
// this page shows an error state rather than stale/empty data if the flag flips off while
// someone's looking at it.
export default function DataBrowser({ onNew, onSelect, onDomainPacks }) {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [files, setFiles]   = useState([])
  const [docs, setDocs]     = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState("")

  const load = useCallback(async () => {
    try {
      const [filesRes, docsRes] = await Promise.all([getDemoDataFiles(), getDemoDocuments()])
      setFiles(filesRes.data)
      setDocs(docsRes.data)
      setError("")
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Failed to load data")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div className="h-screen flex bg-background overflow-hidden font-sans">

      <div className="hidden md:flex w-64 shrink-0 border-r border-border flex-col bg-sidebar">
        <Sidebar onNew={onNew} currentTaskId={null} onSelect={onSelect} onDomainPacks={onDomainPacks} onData={() => {}} activeView="data" />
      </div>

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">

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
                <Sidebar onNew={() => setDrawerOpen(false)} currentTaskId={null} onSelect={onSelect} onDomainPacks={() => { onDomainPacks(); setDrawerOpen(false) }} onData={() => setDrawerOpen(false)} activeView="data" />
              </SheetContent>
            </Sheet>
            <h1 className="text-heading text-foreground leading-none">Available Data</h1>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-8">
          <div className="max-w-4xl mx-auto flex flex-col gap-6">

            <div>
              <h2 className="text-display-sm font-bold text-foreground tracking-tight leading-tight mb-1.5">
                What's already loaded
              </h2>
              <p className="text-body text-muted-foreground leading-relaxed max-w-2xl">
                Datasets and knowledge base documents already in this deployment — ask about
                any of these without uploading anything yourself.
              </p>
            </div>

            {error && <p className="text-sm text-destructive">{error}</p>}

            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-foreground" />
                  <CardTitle className="text-heading">Dataset files ({files.length})</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="pt-0 overflow-x-auto">
                {loading ? (
                  <p className="text-body text-muted-foreground">Loading…</p>
                ) : files.length === 0 ? (
                  <p className="text-body text-muted-foreground">No dataset files loaded yet.</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>Size</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {files.map(f => (
                        <TableRow key={f.name}>
                          <TableCell className="font-mono text-xs">{f.name}</TableCell>
                          <TableCell className="text-caption text-muted-foreground">{formatBytes(f.size_bytes)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-foreground" />
                  <CardTitle className="text-heading">Knowledge base documents ({docs.length})</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="pt-0 overflow-x-auto">
                {loading ? (
                  <p className="text-body text-muted-foreground">Loading…</p>
                ) : docs.length === 0 ? (
                  <p className="text-body text-muted-foreground">No documents uploaded to any domain pack yet.</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>File</TableHead>
                        <TableHead>Pack</TableHead>
                        <TableHead>Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {docs.map(d => (
                        <TableRow key={d.id}>
                          <TableCell>{d.filename}</TableCell>
                          <TableCell className="text-caption text-muted-foreground">{d.pack_name}</TableCell>
                          <TableCell>
                            <Badge variant="outline" className={STATUS_STYLE[d.status] || ""}>{d.status}</Badge>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>

          </div>
        </div>
      </div>
    </div>
  )
}
