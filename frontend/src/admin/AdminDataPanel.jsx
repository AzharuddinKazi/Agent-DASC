import { useCallback, useEffect, useState } from "react"
import { getAdminDocuments, getAdminDataFiles } from "../api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import { Database, FileText } from "lucide-react"

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

// Read-only for this pass (see TASKS.md) — a cross-pack document browser (domain-pack
// knowledge base uploads, which already have per-pack upload/delete elsewhere) plus a
// listing of the raw data/ directory the sandbox/analyzer read directly, which has no
// upload UI anywhere yet.
export default function AdminDataPanel() {
  const [docs, setDocs]       = useState([])
  const [files, setFiles]     = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState("")

  const load = useCallback(async () => {
    try {
      const [docsRes, filesRes] = await Promise.all([getAdminDocuments(), getAdminDataFiles()])
      setDocs(docsRes.data)
      setFiles(filesRes.data)
      setError("")
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Failed to load data")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div className="max-w-4xl mx-auto flex flex-col gap-6 w-full">
      <div>
        <div className="flex items-center gap-2 mb-1.5">
          <Database className="w-5 h-5 text-foreground" />
          <h2 className="text-display-sm font-bold text-foreground tracking-tight leading-tight">Data</h2>
        </div>
        <p className="text-body text-muted-foreground leading-relaxed max-w-xl">
          What's actually in this deployment: raw dataset files the pipeline reads, and
          domain-pack knowledge base documents across every pack.
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
            <p className="text-body text-muted-foreground">No files found in the data directory.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Size</TableHead>
                  <TableHead>Modified</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {files.map(f => (
                  <TableRow key={f.name}>
                    <TableCell className="font-mono text-xs">{f.name}</TableCell>
                    <TableCell className="text-caption text-muted-foreground">{formatBytes(f.size_bytes)}</TableCell>
                    <TableCell className="text-caption text-muted-foreground">
                      {new Date(f.modified_at).toLocaleString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-heading">Knowledge base documents ({docs.length})</CardTitle>
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
                  <TableHead>Chunks</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Uploaded</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {docs.map(d => (
                  <TableRow key={d.id}>
                    <TableCell>{d.filename}</TableCell>
                    <TableCell className="text-caption text-muted-foreground">{d.pack_name}</TableCell>
                    <TableCell className="text-caption text-muted-foreground tabular-nums">{d.chunk_count}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className={STATUS_STYLE[d.status] || ""}>{d.status}</Badge>
                    </TableCell>
                    <TableCell className="text-caption text-muted-foreground">
                      {new Date(d.created_at).toLocaleDateString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
