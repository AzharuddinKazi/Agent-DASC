import { useState } from "react"
import { useAuth } from "../hooks/useAuth"
import { useAdminAccess } from "./useAdminAccess"
import AdminLogin from "./AdminLogin"
import FeatureFlagsPanel from "./FeatureFlagsPanel"
import AdminTasksPanel from "./AdminTasksPanel"
import AdminDomainPacksPanel from "./AdminDomainPacksPanel"
import AdminUsersPanel from "./AdminUsersPanel"
import AdminSystemPanel from "./AdminSystemPanel"
import { Button } from "@/components/ui/button"
import { ShieldCheck, LogOut, ShieldAlert, ToggleLeft, ListChecks, Package, Users, Activity } from "lucide-react"

const SECTIONS = [
  { id: "flags",  label: "Flags",        icon: ToggleLeft,  Component: FeatureFlagsPanel },
  { id: "tasks",  label: "Tasks",        icon: ListChecks,  Component: AdminTasksPanel },
  { id: "packs",  label: "Domain Packs", icon: Package,     Component: AdminDomainPacksPanel },
  { id: "users",  label: "Users",        icon: Users,       Component: AdminUsersPanel },
  { id: "system", label: "System",       icon: Activity,    Component: AdminSystemPanel },
]

function Spinner() {
  return (
    <div className="h-screen flex items-center justify-center bg-background">
      <div className="w-6 h-6 border-2 border-muted-foreground/30 border-t-foreground rounded-full animate-spin" />
    </div>
  )
}

function Shell({ email, onSignOut, section, onSectionChange, children }) {
  return (
    <div className="min-h-screen flex flex-col bg-background font-sans">
      <div className="h-14 border-b border-border bg-card flex items-center justify-between px-6 shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center shrink-0">
            <ShieldCheck className="w-4 h-4 text-primary-foreground" />
          </div>
          <h1 className="text-heading text-foreground leading-none">Admin</h1>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-caption text-muted-foreground">{email}</span>
          <Button variant="ghost" size="icon-sm" className="text-muted-foreground" onClick={onSignOut} title="Sign out">
            <LogOut className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>
      {section && (
        <div className="border-b border-border bg-card px-6 flex items-center gap-1 shrink-0">
          {SECTIONS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => onSectionChange(id)}
              className={`flex items-center gap-1.5 px-3 py-2.5 text-body border-b-2 -mb-px transition-colors cursor-pointer ${
                section === id
                  ? "border-primary text-foreground font-medium"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
            </button>
          ))}
        </div>
      )}
      <div className="flex-1 overflow-y-auto px-6 py-8">{children}</div>
    </div>
  )
}

// Standalone entry point (admin.html / src/admin/main.jsx) — deliberately not a view
// inside App.jsx's SPA. It shares the design system and the Supabase auth backend, but
// has its own login screen, its own layout, and isn't reachable through the main app's
// navigation. Being logged in here still isn't the same as being authorized here — see
// useAdminAccess (the server-side ADMIN_EMAILS allowlist decides that, not this file).
export default function AdminApp() {
  const { user, loading, signOut } = useAuth()
  const { status, flags } = useAdminAccess()
  const [section, setSection] = useState("flags")

  if (loading) return <Spinner />
  if (!user) return <AdminLogin />

  if (status === "checking") return <Spinner />

  if (status === "forbidden") {
    return (
      <Shell email={user.email} onSignOut={signOut}>
        <div className="max-w-md mx-auto flex flex-col items-center text-center gap-3 mt-16">
          <ShieldAlert className="w-8 h-8 text-destructive" />
          <h2 className="text-heading text-foreground">Not authorized</h2>
          <p className="text-body text-muted-foreground">
            {user.email} is signed in but isn't on the admin allowlist for this
            deployment. Ask whoever manages ADMIN_EMAILS to add this account.
          </p>
        </div>
      </Shell>
    )
  }

  if (status === "error") {
    return (
      <Shell email={user.email} onSignOut={signOut}>
        <p className="text-sm text-destructive text-center mt-16">
          Failed to load admin data — is the backend running?
        </p>
      </Shell>
    )
  }

  const Active = SECTIONS.find(s => s.id === section)?.Component || FeatureFlagsPanel

  return (
    <Shell email={user.email} onSignOut={signOut} section={section} onSectionChange={setSection}>
      {section === "flags" ? <FeatureFlagsPanel initialFlags={flags} /> : <Active />}
    </Shell>
  )
}
