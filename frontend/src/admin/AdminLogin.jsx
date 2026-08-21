import { useState } from "react"
import { useAuth } from "../hooks/useAuth"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent } from "@/components/ui/card"
import { ShieldCheck } from "lucide-react"

// Deliberately sign-in only — no "create account" flow. Admin accounts are ordinary
// Supabase accounts (see auth.py:get_current_admin's ADMIN_EMAILS allowlist) that
// already exist; this panel doesn't mint new ones. Whether a signed-in account is
// actually authorized is decided server-side on every request, not here — this screen
// only gets someone as far as "logged in", same as the main app's Login.
export default function AdminLogin() {
  const { signIn } = useAuth()
  const [email, setEmail]       = useState("")
  const [password, setPassword] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError]       = useState("")

  const handleSubmit = async e => {
    e.preventDefault()
    if (!email.trim() || !password.trim() || isSubmitting) return
    setIsSubmitting(true)
    setError("")
    const { error: err } = await signIn(email.trim(), password)
    setIsSubmitting(false)
    if (err) setError(err.message)
  }

  return (
    <div className="h-screen flex items-center justify-center bg-background font-sans px-6">
      <div className="w-full max-w-[380px] flex flex-col gap-6">
        <div className="text-center">
          <div className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center mx-auto mb-3">
            <ShieldCheck className="w-5 h-5 text-primary-foreground" />
          </div>
          <h1 className="text-display-sm text-foreground tracking-tight">Admin</h1>
          <p className="text-body text-muted-foreground mt-1">Deployment-wide settings</p>
        </div>

        <Card className="shadow-sm border-border">
          <CardContent className="p-6">
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="email" className="text-xs">Email</Label>
                <Input
                  id="email" type="email" autoComplete="email" required
                  value={email} onChange={e => setEmail(e.target.value)}
                  placeholder="you@example.com"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="password" className="text-xs">Password</Label>
                <Input
                  id="password" type="password" autoComplete="current-password" required
                  value={password} onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                />
              </div>

              {error && <p className="text-caption text-destructive">{error}</p>}

              <Button type="submit" disabled={isSubmitting} className="w-full">
                {isSubmitting ? "Please wait…" : "Sign in"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
