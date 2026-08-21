// Shared status vocabulary for tasks.status ("running"|"completed"|"failed"|"stopped"|
// "paused"|"awaiting_review") — single source of truth for label/badge/dot styling, used
// by Sidebar.jsx, Dashboard.jsx, and the admin Tasks panel so a new status only needs to
// be added here instead of drifting across separately-maintained copies.
export const STATUS_META = {
  running:         { label: "Running",         badge: "bg-blue-50 text-blue-600 border-blue-200",      dot: "bg-info animate-pulse" },
  completed:       { label: "Complete",        badge: "bg-success/10 text-success border-success/30",  dot: "bg-success" },
  failed:          { label: "Failed",          badge: "bg-danger/10 text-danger border-danger/30",     dot: "bg-danger" },
  stopped:         { label: "Stopped",         badge: "bg-muted text-muted-foreground border-border",  dot: "bg-neutral-400" },
  paused:          { label: "Paused",          badge: "bg-amber-50 text-amber-600 border-amber-200",   dot: "bg-amber-400" },
  awaiting_review: { label: "Awaiting Review", badge: "bg-indigo-50 text-indigo-600 border-indigo-200", dot: "bg-indigo-400" },
}

const FALLBACK = { label: "Unknown", badge: "bg-muted text-muted-foreground border-border", dot: "bg-neutral-400" }

export function statusMeta(status) {
  return STATUS_META[status] || { ...FALLBACK, label: status || FALLBACK.label }
}
