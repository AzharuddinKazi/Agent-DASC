export const AGENT_MESSAGES = {
  analyzer:  "Profiling your data files...",
  planner:   "Planning the analysis approach...",
  coder:     "Writing analysis code...",
  executor:  "Running the analysis...",
  verifier:  "Checking result quality...",
  router:    "Refining the approach, starting next round...",
  finalizer: "Preparing your report...",
}

export const AGENT_ORDER = ["analyzer", "planner", "coder", "executor", "verifier", "router", "finalizer"]

export const AGENT_ICONS = {
  analyzer:  "ti-scan",
  planner:   "ti-list",
  coder:     "ti-code",
  executor:  "ti-player-play",
  verifier:  "ti-shield-check",
  router:    "ti-refresh",
  finalizer: "ti-sparkles",
}