import { useEffect, useState } from "react"
import { getDomainPacks, domainPackDownloadUrl } from "../../api"
import Sidebar from "./Sidebar"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from "@/components/ui/sheet"
import { Menu, Package, Download } from "lucide-react"

export default function DomainPacks({ onNew, onSelect }) {
  const [packs, setPacks]     = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState("")
  const [drawerOpen, setDrawerOpen] = useState(false)

  useEffect(() => {
    getDomainPacks()
      .then(r => setPacks(r.data))
      .catch(err => setError(err?.message || "Failed to load domain packs — is the backend running?"))
      .finally(() => setLoading(false))
  }, [])

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
                industry, and include a matching example dataset generator. Download a pack and drop
                its files into your installation to switch domains.
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
                    <div className="w-9 h-9 rounded-lg bg-accent flex items-center justify-center mb-2">
                      <Package className="w-4.5 h-4.5 text-foreground" />
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
                    <Button asChild size="sm" className="gap-1.5 self-start">
                      <a href={domainPackDownloadUrl(pack.id)} download>
                        <Download className="w-3.5 h-3.5" />
                        Download .zip
                      </a>
                    </Button>
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
