import { useEffect, useRef, useState } from "react"
import { brand } from "../../config/brand"
import { loginWithGoogle, loginAsGuest, getLoginOptions } from "../../api"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID

// Google Identity Services — a single script tag (loaded once from index.html), no npm
// package, no OAuth redirect dance. The rendered button hands back a signed credential JWT
// directly; this component's only job is forwarding it to the backend (which verifies it
// server-side and sets the real session cookie) and telling the caller once that's done.
//
// A second, much weaker path can sit below it: name-only "continue as guest", for people
// on office laptops where Gmail (and so Google sign-in) is deactivated. Nothing verifies
// the name — it exists so those colleagues can open and try the app during a demo, not to
// establish real identity (see backend/main.py's auth_guest). Gated behind demo_mode: the
// operator turns it on only while actively demoing, so it isn't a standing weaker login
// path the rest of the time. guestLoginEnabled comes from an unauthenticated endpoint
// (/auth/login_options) since this screen runs before anyone has a session — the regular
// /features endpoint requires being signed in already.
export default function Login({ onSignedIn }) {
  const buttonRef = useRef(null)
  const [error, setError] = useState("")
  const [verifying, setVerifying] = useState(false)

  const [guestLoginEnabled, setGuestLoginEnabled] = useState(false)
  const [guestName, setGuestName] = useState("")
  const [guestBusy, setGuestBusy] = useState(false)
  const [guestError, setGuestError] = useState("")

  useEffect(() => {
    let cancelled = false
    getLoginOptions()
      .then(r => { if (!cancelled) setGuestLoginEnabled(!!r.data.guest_login_enabled) })
      .catch(() => { /* leave it hidden on a fetch error rather than risk exposing it */ })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return
    let cancelled = false

    const handleCredential = async (response) => {
      setVerifying(true)
      setError("")
      try {
        await loginWithGoogle(response.credential)
        if (!cancelled) onSignedIn()
      } catch (err) {
        if (!cancelled) {
          setError(err?.response?.data?.detail || "Sign-in failed — please try again.")
          setVerifying(false)
        }
      }
    }

    const render = () => {
      if (cancelled || !window.google?.accounts?.id || !buttonRef.current) return
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: handleCredential,
      })
      window.google.accounts.id.renderButton(buttonRef.current, {
        theme: "outline", size: "large", width: 280,
      })
    }

    // The GSI script (index.html) loads async — poll briefly rather than assuming it's
    // ready by the time this component mounts.
    if (window.google?.accounts?.id) render()
    else {
      const t = setInterval(() => {
        if (window.google?.accounts?.id) { clearInterval(t); render() }
      }, 100)
      return () => { cancelled = true; clearInterval(t) }
    }
    return () => { cancelled = true }
  }, [onSignedIn])

  const handleGuestSubmit = async (e) => {
    e.preventDefault()
    const name = guestName.trim()
    if (!name) return
    setGuestBusy(true)
    setGuestError("")
    try {
      await loginAsGuest(name)
      onSignedIn()
    } catch (err) {
      setGuestError(err?.response?.data?.detail || "Couldn't continue — please try again.")
      setGuestBusy(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-subtle px-4">
      <Card className="w-full max-w-sm p-8 flex flex-col items-center gap-6 text-center">
        <div className="w-12 h-12 rounded-xl bg-primary flex items-center justify-center">
          <span className="text-label font-black text-primary-foreground leading-none">{brand.appShortCode}</span>
        </div>
        <div>
          <h1 className="text-heading font-bold text-foreground">{brand.appName}</h1>
          <p className="text-body text-muted-foreground mt-1">{brand.tagline}</p>
        </div>

        {GOOGLE_CLIENT_ID ? (
          <>
            <div ref={buttonRef} className={verifying ? "opacity-50 pointer-events-none" : ""} />
            {verifying && <p className="text-sm text-muted-foreground">Signing in…</p>}
            {error && <p className="text-sm text-destructive">{error}</p>}
          </>
        ) : (
          <p className="text-sm text-destructive">
            Sign-in isn't configured yet — VITE_GOOGLE_CLIENT_ID is missing. See
            frontend/.env.example for how to create a Google OAuth Client ID.
          </p>
        )}

        {guestLoginEnabled && (
          <>
            <div className="w-full flex items-center gap-3 text-caption text-muted-foreground">
              <div className="h-px flex-1 bg-border" />
              <span>or</span>
              <div className="h-px flex-1 bg-border" />
            </div>

            <form onSubmit={handleGuestSubmit} className="w-full flex flex-col gap-2">
              <Input
                type="text"
                placeholder="Your name"
                value={guestName}
                onChange={(e) => setGuestName(e.target.value)}
                disabled={guestBusy}
                maxLength={100}
                required
              />
              <Button type="submit" variant="outline" className="w-full" disabled={guestBusy || !guestName.trim()}>
                {guestBusy ? "Continuing…" : "Continue with just your name"}
              </Button>
              <p className="text-caption text-muted-foreground">
                No Gmail on this machine? Enter your name to try the app — nothing else is
                checked or required.
              </p>
              {guestError && <p className="text-sm text-destructive">{guestError}</p>}
            </form>
          </>
        )}
      </Card>
    </div>
  )
}
