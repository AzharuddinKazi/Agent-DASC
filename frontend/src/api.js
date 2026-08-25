import axios from "axios"

export const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000"
// withCredentials: the `session` cookie real Google login sets (see auth.py) is
// cross-origin (frontend :5174, backend :8000) — without this, the browser never sends or
// accepts it, and every authenticated request would silently 401.
const API = axios.create({ baseURL: API_BASE, withCredentials: true })

export const submitTask  = (query, formatting_guidelines, task_type = "qa", require_human_review = false, domain_pack_id = null) =>
  API.post("/api/v1/submit_task", { query, formatting_guidelines, task_type, require_human_review, domain_pack_id })
// Clarification is a nice-to-have that runs a "medium" tier LLM call (occasionally two,
// on a malformed-output retry) before the user sees anything — under free-tier OpenRouter
// congestion this can occasionally take 15-20s+. An 8s bound was previously used, but it
// was silently skipping clarification for genuinely ambiguous queries whenever the model
// was just slow (not wrong) — verified against a real run where the actual response
// arrived successfully at 16s, 8s after the frontend had already given up on it. Raised
// to 15s, paired with a visible "Checking…" state at the call site (not a bare disabled
// button) so the longer wait doesn't read as stuck.
export const clarifyTask = (query, task_type = "qa", domain_pack_id = null) =>
  API.post("/api/v1/clarify_task", { query, task_type, domain_pack_id }, { timeout: 15000 })
export const getTasks    = () => API.get("/api/v1/get_tasks")
export const getTask     = (id) => API.get(`/api/v1/get_task/${id}`)
// Blob response — the file needs the session cookie (withCredentials, see API above), so
// this can't just be a plain <a href> like domainPackDownloadUrl below; the caller turns
// the blob into an object URL and triggers the download itself (see ReportView.jsx).
export const exportReportDocx = (id) => API.get(`/api/v1/get_task/${id}/export.docx`, { responseType: "blob" })
export const stopTask    = (id) => API.post(`/api/v1/tasks/${id}/stop`)
export const pauseTask   = (id) => API.post(`/api/v1/tasks/${id}/pause`)
export const resumeTask  = (id) => API.post(`/api/v1/tasks/${id}/resume`)
export const submitReviewDecision = (id, decision) => API.post(`/api/v1/tasks/${id}/review`, { decision })
export const checkHealth = () => API.get("/health")

export const getDomainPacks       = () => API.get("/api/v1/domain_packs")
export const getDomainPackConfig  = (id) => API.get(`/api/v1/domain_packs/${id}/config`)
export const domainPackDownloadUrl = (id) => `${API_BASE}/api/v1/domain_packs/${id}/download`
export const activateDomainPack   = (id) => API.post(`/api/v1/domain_packs/${id}/activate`)
export const deactivateDomainPack = () => API.post(`/api/v1/domain_packs/deactivate`)

// Any signed-in user can read which features are on — needed to correctly hide/show
// their own UI (Sidebar's Domain Packs link, EmptyState's status bar, etc.). Distinct
// from getFeatureFlags below, which useAdminAccess.js relies on 403ing for non-admins.
export const listFeatures = () => API.get("/api/v1/features")

export const getFeatureFlags = () => API.get("/api/v1/admin/features")
export const setFeatureFlag  = (feature, enabled) => API.post(`/api/v1/admin/features/${feature}`, { enabled })

export const getAdminTasks   = (params = {}) => API.get("/api/v1/admin/tasks", { params })
export const getAdminTask    = (id) => API.get(`/api/v1/admin/tasks/${id}`)
export const stopAdminTask   = (id) => API.post(`/api/v1/admin/tasks/${id}/stop`)
export const rerunAdminTask  = (id) => API.post(`/api/v1/admin/tasks/${id}/rerun`)
export const deleteAdminTask = (id) => API.delete(`/api/v1/admin/tasks/${id}`)

export const getAdminDomainPacks = () => API.get("/api/v1/admin/domain_packs")
export const createDomainPack = (data) => API.post("/api/v1/admin/domain_packs", data)
export const updateDomainPack = (id, data) => API.put(`/api/v1/admin/domain_packs/${id}`, data)
export const deleteDomainPack = (id) => API.delete(`/api/v1/admin/domain_packs/${id}`)

export const getAdminUsers = () => API.get("/api/v1/admin/users")
export const banUser       = (id) => API.post(`/api/v1/admin/users/${id}/ban`)
export const unbanUser     = (id) => API.post(`/api/v1/admin/users/${id}/unban`)
export const getAdminList  = () => API.get("/api/v1/admin/admins")

export const getAdminSystem = () => API.get("/api/v1/admin/system")

export const loginWithGoogle = (credential) => API.post("/api/v1/auth/google", { credential })
export const loginAsGuest    = (name) => API.post("/api/v1/auth/guest", { name })
export const getLoginOptions = () => API.get("/api/v1/auth/login_options")
export const logout          = () => API.post("/api/v1/auth/logout")
export const getMe           = () => API.get("/api/v1/auth/me")

export const getAdminPrompts   = () => API.get("/api/v1/admin/prompts")
export const setAdminPrompt    = (agent, prompt_text) => API.put(`/api/v1/admin/prompts/${agent}`, { prompt_text })
export const resetAdminPrompt  = (agent) => API.post(`/api/v1/admin/prompts/${agent}/reset`)

export const getAdminModels        = () => API.get("/api/v1/admin/models")
export const setAdminModelOverride = (agent, model_id) => API.put(`/api/v1/admin/models/${agent}`, { model_id })
export const setLlmSpeedProfile    = (profile) => API.post("/api/v1/llm_speed_profile", { profile })

export const getAdminDocuments = () => API.get("/api/v1/admin/documents")
export const getAdminDataFiles = () => API.get("/api/v1/admin/data-files")

// Demo-mode equivalents — same data, open to every signed-in user, but only while an
// admin has demo_mode toggled on (see useFeatureFlags). 403s otherwise.
export const getDemoDataFiles = () => API.get("/api/v1/demo/data-files")
export const getDemoDocuments = () => API.get("/api/v1/demo/documents")

export const getPackDocuments = (packId) => API.get(`/api/v1/domain_packs/${packId}/documents`)
export const uploadPackDocument = (packId, file) => {
  const form = new FormData()
  form.append("file", file)
  return API.post(`/api/v1/domain_packs/${packId}/documents`, form)
}
export const deletePackDocument = (packId, docId) =>
  API.delete(`/api/v1/domain_packs/${packId}/documents/${docId}`)