import { useCallback, useEffect, useState } from "react"
import { getAdminModels, setAdminModelOverride, setLlmSpeedProfile } from "../api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import { Cpu, Zap, Gift } from "lucide-react"

const SPEED_PROFILES = [
  {
    id: "free", label: "Free", icon: Gift,
    description: "OpenRouter's free-tier models. No billing account needed, but rate-limited and can be slower/queued under shared-pool load.",
  },
  {
    id: "fast_paid", label: "Fast (paid)", icon: Zap,
    description: "Billed OpenRouter models, picked for cheapest-and-still-fast — roughly $0.02/$0.04 per million input/output tokens as of when this was built (verify current pricing at openrouter.ai before relying on it). A full pipeline run costs a small fraction of a cent, but it is real money on your OpenRouter account, not free-tier.",
  },
]

const TIER_COLOR = {
  high:   "bg-purple-100 text-purple-700 border-purple-200",
  medium: "bg-blue-100 text-blue-700 border-blue-200",
  low:    "bg-neutral-100 text-neutral-700 border-neutral-200",
}

// Extends llm_router.py's existing per-agent override pattern (today only settable via
// OPENROUTER_MODEL_CODER) with a DB-backed one, checked first — see
// llm_router.get_model_override(). Dropdown is populated from whatever the configured
// OpenAI-compatible endpoint's live Ollama tag list actually is, so this can't typo a
// model id that doesn't exist on this machine.
export default function AdminModelsPanel() {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy]       = useState(null)
  const [error, setError]     = useState("")

  // Draft/baseline split, same pattern as FeatureFlagsPanel: picking a profile below
  // only stages it — nothing actually changes (and no billed model gets called) until
  // "Save changes" is clicked. Deliberately not instant-on-click given fast_paid means
  // real OpenRouter billing, not just a cosmetic preference.
  const [draftProfile, setDraftProfile] = useState(null)
  const [savingProfile, setSavingProfile] = useState(false)

  const load = useCallback(async () => {
    try {
      const r = await getAdminModels()
      setData(r.data)
      setDraftProfile(r.data.llm_speed_profile)
      setError("")
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Failed to load models")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleChange = async (agent, modelId) => {
    setBusy(agent)
    try {
      await setAdminModelOverride(agent, modelId || null)
      await load()
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Update failed")
    } finally {
      setBusy(null)
    }
  }

  const profileDirty = data && draftProfile !== data.llm_speed_profile

  const handleSaveProfile = async () => {
    setSavingProfile(true)
    setError("")
    try {
      await setLlmSpeedProfile(draftProfile)
      await load()
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Failed to update speed profile")
    } finally {
      setSavingProfile(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto flex flex-col gap-6 w-full">
      <div>
        <div className="flex items-center gap-2 mb-1.5">
          <Cpu className="w-5 h-5 text-foreground" />
          <h2 className="text-display-sm font-bold text-foreground tracking-tight leading-tight">Models</h2>
        </div>
        <p className="text-body text-muted-foreground leading-relaxed max-w-xl">
          Which model each agent actually calls. Overriding an agent here takes effect on
          its very next call — no restart needed.
        </p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading ? (
        <p className="text-body text-muted-foreground">Loading…</p>
      ) : (
        <>
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-start justify-between gap-4">
              <div>
                <CardTitle className="text-heading">Speed profile</CardTitle>
                <p className="text-caption text-muted-foreground mt-1 max-w-md">
                  Which model tier every agent draws from. Applies to the very next LLM
                  call once saved — no restart needed.
                </p>
              </div>
              {profileDirty && (
                <div className="flex items-center gap-2 shrink-0">
                  <Button
                    size="sm" variant="outline" disabled={savingProfile}
                    onClick={() => setDraftProfile(data.llm_speed_profile)}
                  >
                    Discard
                  </Button>
                  <Button size="sm" disabled={savingProfile} onClick={handleSaveProfile}>
                    {savingProfile ? "Saving…" : "Save changes"}
                  </Button>
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent className="pt-0 flex flex-col gap-2">
            {SPEED_PROFILES.map(p => {
              const Icon = p.icon
              const selected = draftProfile === p.id
              return (
                <button
                  key={p.id}
                  onClick={() => setDraftProfile(p.id)}
                  disabled={savingProfile}
                  className={`text-left flex items-start gap-3 rounded-md border px-3 py-2.5 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
                    selected
                      ? "border-primary bg-primary/5"
                      : "border-border hover:bg-accent/40"
                  }`}
                >
                  <Icon className="w-4 h-4 mt-0.5 shrink-0 text-foreground" />
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-body font-semibold text-foreground">{p.label}</span>
                      {data.llm_speed_profile === p.id && (
                        <Badge variant="outline" className="text-label">Active</Badge>
                      )}
                    </div>
                    <p className="text-caption text-muted-foreground leading-relaxed mt-0.5">
                      {p.description}
                    </p>
                  </div>
                </button>
              )
            })}
            {draftProfile === "fast_paid" && data.llm_speed_profile !== "fast_paid" && (
              <p className="text-caption text-warning mt-1">
                Saving this switches every agent onto billed OpenRouter models on their
                very next call. Switch back to Free any time — it applies just as fast.
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-heading">Agents ({data.agents.length})</CardTitle>
          </CardHeader>
          <CardContent className="pt-0 overflow-x-auto">
            {data.available_models.length === 0 && (
              <p className="text-caption text-muted-foreground mb-3">
                No live model list found at the configured endpoint — overrides can still be
                typed once a dropdown option exists, but none were discovered right now (is
                this endpoint an Ollama server?).
              </p>
            )}
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Agent</TableHead>
                  <TableHead>Tier</TableHead>
                  <TableHead>Effective model</TableHead>
                  <TableHead>Override</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.agents.map(a => (
                  <TableRow key={a.agent_name}>
                    <TableCell className="capitalize">{a.agent_name.replace(/_/g, " ")}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className={TIER_COLOR[a.tier] || ""}>{a.tier}</Badge>
                    </TableCell>
                    <TableCell className="text-caption text-muted-foreground truncate max-w-56">
                      {a.effective_model || "—"}
                    </TableCell>
                    <TableCell>
                      <select
                        className="h-8 rounded-md border border-input bg-background px-2 text-caption disabled:opacity-50"
                        value={a.db_override || ""}
                        disabled={busy === a.agent_name}
                        onChange={e => handleChange(a.agent_name, e.target.value)}
                      >
                        <option value="">Default ({a.tier} tier)</option>
                        {data.available_models.map(m => (
                          <option key={m} value={m}>{m}</option>
                        ))}
                      </select>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
        </>
      )}
    </div>
  )
}
