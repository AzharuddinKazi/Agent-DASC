import axios from "axios"
import { supabase } from "./lib/supabaseClient"

export const API_BASE = "http://localhost:8000"
const API = axios.create({ baseURL: API_BASE })

API.interceptors.request.use(async config => {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export const submitTask  = (query, formatting_guidelines, task_type = "qa") =>
  API.post("/api/v1/submit_task", { query, formatting_guidelines, task_type })
export const getTasks    = () => API.get("/api/v1/get_tasks")
export const getTask     = (id) => API.get(`/api/v1/get_task/${id}`)
export const checkHealth = () => API.get("/health")

export const getDomainPacks       = () => API.get("/api/v1/domain_packs")
export const domainPackDownloadUrl = (id) => `${API_BASE}/api/v1/domain_packs/${id}/download`