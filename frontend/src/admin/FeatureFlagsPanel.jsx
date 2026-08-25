import { useCallback, useEffect, useMemo, useState } from "react"
import { setFeatureFlag } from "../api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { Button } from "@/components/ui/button"
import { ShieldCheck, Package, Database } from "lucide-react"

// Client-side display copy for each known backend flag — new flags added to
// feature_flags.KNOWN_FEATURES without an entry here still render (with the raw id as
// a fallback label) so this page never silently hides a real toggle.
const FEATURE_META = {
  domain_packs: {
    label: "Domain Packs",
    description:
      "Industry-specific prompt config, sub-question dimensions, and knowledge-base " +
      "grounding for the Planner/Coder/Verifier. Turning this off reverts every task to " +
      "the generic, domain-agnostic pipeline — the Domain Packs page is hidden from the " +
      "sidebar, and its API rejects requests with 403 while off.",
    icon: Package,
  },
  demo_mode: {
    label: "Demo Mode",
    description:
      "Two things at once, both off by default: (1) shows the \"continue with just your " +
      "name\" login option — with this off, only Google sign-in works, name-only login " +
      "403s even if someone already has the link; (2) adds an \"Available Data\" page to " +
      "every signed-in user's sidebar, listing which dataset files and knowledge-base " +
      "documents are already loaded. Toggle on only while actively demoing, off after.",
    icon: Database,
  },
}

export default function FeatureFlagsPanel({ initialFlags }) {
  // "baseline" is the last-known-saved state; "draft" is what the toggles show,
  // diverging from baseline the moment a switch flips and only reconciling on Save or
  // Discard. No background polling here (unlike the main app's sidebar hook) — this
  // panel owns the authoritative fetch (useAdminAccess's probe call), so a second timer
  // re-fetching the same thing would just risk clobbering an in-progress edit for no
  // benefit in a page nobody else is meant to have open at the same time.
  const [baseline, setBaseline] = useState(initialFlags)
  const [draft, setDraft]       = useState(initialFlags)
  const [saving, setSaving]     = useState(false)
  const [error, setError]       = useState("")

  useEffect(() => { setBaseline(initialFlags); setDraft(initialFlags) }, [initialFlags])

  const dirty = useMemo(
    () => Object.keys(draft).filter(name => draft[name] !== baseline[name]),
    [draft, baseline]
  )

  const handleToggle = useCallback((name, enabled) => {
    setDraft(d => ({ ...d, [name]: enabled }))
  }, [])

  const handleDiscard = useCallback(() => {
    setDraft(baseline)
    setError("")
  }, [baseline])

  const handleSave = useCallback(async () => {
    setSaving(true)
    setError("")
    try {
      await Promise.all(dirty.map(name => setFeatureFlag(name, draft[name])))
      setBaseline(b => ({ ...b, ...Object.fromEntries(dirty.map(name => [name, draft[name]])) }))
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Failed to save changes")
    } finally {
      setSaving(false)
    }
  }, [dirty, draft])

  const featureNames = Object.keys(draft)

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-6 w-full">

      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <ShieldCheck className="w-5 h-5 text-foreground" />
            <h2 className="text-display-sm font-bold text-foreground tracking-tight leading-tight">
              Feature flags
            </h2>
          </div>
          <p className="text-body text-muted-foreground leading-relaxed max-w-xl">
            Turn app features on or off deployment-wide. Changes apply only after you
            click Save — nothing here is live until then.
          </p>
        </div>
        {dirty.length > 0 && (
          <div className="flex items-center gap-2 shrink-0">
            <Button size="sm" variant="outline" disabled={saving} onClick={handleDiscard}>
              Discard
            </Button>
            <Button size="sm" disabled={saving} onClick={handleSave}>
              {saving ? "Saving…" : "Save changes"}
            </Button>
          </div>
        )}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {featureNames.length === 0 && (
        <p className="text-sm text-muted-foreground">No feature flags defined.</p>
      )}

      <div className="flex flex-col gap-3">
        {featureNames.map(name => {
          const meta = FEATURE_META[name] || { label: name, description: "" }
          const Icon = meta.icon || ShieldCheck
          const enabled = !!draft[name]
          const isDirty = dirty.includes(name)
          return (
            <Card key={name} className={isDirty ? "border-primary/50" : ""}>
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center shrink-0">
                      <Icon className="w-4 h-4 text-foreground" />
                    </div>
                    <CardTitle className="text-heading flex items-center gap-2">
                      {meta.label}
                      {isDirty && (
                        <span className="text-label font-normal text-primary">(unsaved)</span>
                      )}
                    </CardTitle>
                  </div>
                  <Switch
                    checked={enabled}
                    disabled={saving}
                    onCheckedChange={val => handleToggle(name, val)}
                  />
                </div>
              </CardHeader>
              {meta.description && (
                <CardContent className="pt-0">
                  <p className="text-body text-muted-foreground leading-relaxed">
                    {meta.description}
                  </p>
                </CardContent>
              )}
            </Card>
          )
        })}
      </div>
    </div>
  )
}
