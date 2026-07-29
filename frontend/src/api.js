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

export const submitTask  = (query, formatting_guidelines, task_type = "qa") =>
  API.post("/api/v1/submit_task", { query, formatting_guidelines, task_type })
// Clarification is a nice-to-have that runs a "medium" tier LLM call (occasionally two,
// on a malformed-output retry) before the user sees anything — under free-tier OpenRouter
// congestion this can occasionally take 30s+. Bounded to 8s here so a slow/rate-limited
// backend degrades to "just skip the popup," never to "the Analyse button looks stuck."
export const clarifyTask = (query, task_type = "qa", domain_pack_id = null) =>
  API.post("/api/v1/clarify_task", { query, task_type, domain_pack_id }, { timeout: 8000 })
export const getTasks    = () => API.get("/api/v1/get_tasks")
export const getTask     = (id) => API.get(`/api/v1/get_task/${id}`)
export const stopTask    = (id) => API.post(`/api/v1/tasks/${id}/stop`)
export const pauseTask   = (id) => API.post(`/api/v1/tasks/${id}/pause`)
export const resumeTask  = (id) => API.post(`/api/v1/tasks/${id}/resume`)
export const checkHealth = () => API.get("/health")

export const getDomainPacks       = () => API.get("/api/v1/domain_packs")
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