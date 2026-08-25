import { useCallback, useEffect, useState } from "react"
import { getAdminPrompts, setAdminPrompt, resetAdminPrompt } from "../api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { MessageSquareCode, RotateCcw } from "lucide-react"

// Each agent's prompt is still a hardcoded Python constant — this only lays an optional
// DB-backed override on top (agent_prompts table), so an empty table changes nothing.
// planner/writer aren't listed here on purpose — see backend/agents/prompt_store.py's
// module docstring for why (multi-template prompts, not one editable string each).
export default function AdminPromptsPanel() {
  const [prompts, setPrompts] = useState([])
  const [active, setActive]   = useState(null)
  const [draft, setDraft]     = useState("")
  const [loading, setLoading] = useState(true)
  const [saving, setSaving]   = useState(false)
  const [error, setError]     = useState("")
  const [showDefault, setShowDefault] = useState(false)

  const load = useCallback(async (selectAgent) => {
    try {
      const r = await getAdminPrompts()
      setPrompts(r.data)
      const target = r.data.find(p => p.agent_name === selectAgent) || r.data[0]
      if (target) { setActive(target.agent_name); setDraft(target.prompt_text) }
      setError("")
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Failed to load prompts")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const activePrompt = prompts.find(p => p.agent_name === active)
  const dirty = activePrompt && draft !== activePrompt.prompt_text

  const selectAgent = (agent) => {
    const p = prompts.find(x => x.agent_name === agent)
    setActive(agent)
    setDraft(p.prompt_text)
    setShowDefault(false)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await setAdminPrompt(active, draft)
      await load(active)
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Save failed")
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    setSaving(true)
    try {
      await resetAdminPrompt(active)
      await load(active)
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Reset failed")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-5xl mx-auto flex flex-col gap-6 w-full">
      <div>
        <div className="flex items-center gap-2 mb-1.5">
          <MessageSquareCode className="w-5 h-5 text-foreground" />
          <h2 className="text-display-sm font-bold text-foreground tracking-tight leading-tight">Prompts</h2>
        </div>
        <p className="text-body text-muted-foreground leading-relaxed max-w-xl">
          Edit the instructions each agent sends to the model. Changes apply to the very
          next run — no restart needed. A bad edit degrades every task silently, so double
          check before saving.
        </p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading ? (
        <p className="text-body text-muted-foreground">Loading…</p>
      ) : (
        <div className="grid grid-cols-[220px_1fr] gap-4 items-start">
          <Card className="p-0 overflow-hidden">
            <div className="flex flex-col">
              {prompts.map(p => (
                <button
                  key={p.agent_name}
                  onClick={() => selectAgent(p.agent_name)}
                  className={`text-left px-3 py-2.5 text-body border-b border-border last:border-b-0 cursor-pointer transition-colors ${
                    active === p.agent_name
                      ? "bg-accent text-accent-foreground font-medium"
                      : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="capitalize">{p.agent_name.replace(/_/g, " ")}</span>
                    {p.is_customized && <Badge variant="outline" className="shrink-0">Edited</Badge>}
                  </div>
                </button>
              ))}
            </div>
          </Card>

          {activePrompt && (
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between gap-2">
                  <CardTitle className="text-heading capitalize">{active.replace(/_/g, " ")}</CardTitle>
                  <div className="flex items-center gap-2">
                    {activePrompt.is_customized && (
                      <button
                        onClick={() => setShowDefault(s => !s)}
                        className="text-caption text-muted-foreground hover:text-foreground underline underline-offset-2"
                      >
                        {showDefault ? "Hide default" : "View default"}
                      </button>
                    )}
                    {activePrompt.updated_at && (
                      <span className="text-caption text-muted-foreground">
                        Edited {new Date(activePrompt.updated_at).toLocaleString()}
                        {activePrompt.updated_by ? ` by ${activePrompt.updated_by}` : ""}
                      </span>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-0 flex flex-col gap-3">
                {showDefault && (
                  <div className="rounded-md border border-border bg-muted/40 p-3">
                    <p className="text-caption text-muted-foreground mb-1.5">Default prompt</p>
                    <pre className="text-xs whitespace-pre-wrap text-muted-foreground max-h-48 overflow-y-auto">
                      {activePrompt.default_text}
                    </pre>
                  </div>
                )}
                <Textarea
                  value={draft}
                  onChange={e => setDraft(e.target.value)}
                  className="min-h-80 font-mono text-xs"
                />
                <div className="flex items-center gap-2 justify-end">
                  {activePrompt.is_customized && (
                    <Button variant="outline" size="sm" disabled={saving} onClick={handleReset}>
                      <RotateCcw className="w-3.5 h-3.5" /> Reset to default
                    </Button>
                  )}
                  <Button size="sm" disabled={!dirty || saving} onClick={handleSave}>
                    {saving ? "Saving…" : "Save"}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
