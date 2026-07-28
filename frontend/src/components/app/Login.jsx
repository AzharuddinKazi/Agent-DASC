import { useState } from "react"
import { useAuth } from "../../hooks/useAuth"
import { brand } from "../../config/brand"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent } from "@/components/ui/card"

export default function Login() {
  const { signIn, signUp } = useAuth()
  const [mode, setMode]         = useState("signin") // "signin" | "signup"
  const [email, setEmail]       = useState("")
  const [password, setPassword] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError]       = useState("")
  const [notice, setNotice]     = useState("")

  const handleSubmit = async e => {
    e.preventDefault()
    if (!email.trim() || !password.trim() || isSubmitting) return
    setIsSubmitting(true)
    setError("")
    setNotice("")
    const { error: err } = mode === "signin"
      ? await signIn(email.trim(), password)
      : await signUp(email.trim(), password)
    setIsSubmitting(false)
    if (err) {
      setError(err.message)
      return
    }
    if (mode === "signup") {
      setNotice("Check your email to confirm your account, then sign in.")
      setMode("signin")
    }
  }

  return (
    <div className="h-screen flex items-center justify-center bg-background font-sans px-6">
      <div className="w-full max-w-[380px] flex flex-col gap-6">
        <div className="text-center">
          <div className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center mx-auto mb-3">
            <span className="text-label font-black text-primary-foreground leading-none">{brand.appShortCode}</span>
          </div>
          <h1 className="text-display-sm text-foreground tracking-tight">{brand.appName}</h1>
          <p className="text-body text-muted-foreground mt-1">{brand.tagline}</p>
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
                  id="password" type="password"
                  autoComplete={mode === "signin" ? "current-password" : "new-password"}
                  required minLength={6}
                  value={password} onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                />
              </div>

              {error && <p className="text-caption text-destructive">{error}</p>}
              {notice && <p className="text-caption text-success">{notice}</p>}

              <Button type="submit" disabled={isSubmitting} className="w-full">
                {isSubmitting ? "Please wait…" : mode === "signin" ? "Sign in" : "Create account"}
              </Button>
            </form>

            <p className="text-caption text-muted-foreground text-center mt-4">
              {mode === "signin" ? "Don't have an account?" : "Already have an account?"}{" "}
              <button
                type="button"
                onClick={() => { setMode(m => m === "signin" ? "signup" : "signin"); setError(""); setNotice("") }}
                className="text-foreground font-medium underline underline-offset-2"
              >
                {mode === "signin" ? "Create one" : "Sign in"}
              </button>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
