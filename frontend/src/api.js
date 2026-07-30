import axios from "axios"
import { supabase } from "./lib/supabaseClient"

export const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000"
const API = axios.create({ baseURL: API_BASE })

API.interceptors.request.use(async config => {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

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

export const getPackDocuments = (packId) => API.get(`/api/v1/domain_packs/${packId}/documents`)
export const uploadPackDocument = (packId, file) => {
  const form = new FormData()
  form.append("file", file)
  return API.post(`/api/v1/domain_packs/${packId}/documents`, form)
}
export const deletePackDocument = (packId, docId) =>
  API.delete(`/api/v1/domain_packs/${packId}/documents/${docId}`)