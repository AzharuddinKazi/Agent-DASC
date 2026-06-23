import axios from "axios"

const API = axios.create({ baseURL: "http://localhost:8000" })

export const submitTask  = (query, formatting_guidelines, task_type = "qa") =>
  API.post("/api/v1/submit_task", { query, formatting_guidelines, task_type })
export const getTasks    = () => API.get("/api/v1/get_tasks")
export const getTask     = (id) => API.get(`/api/v1/get_task/${id}`)
export const checkHealth = () => API.get("/health")