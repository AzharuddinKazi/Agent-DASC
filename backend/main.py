from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agents.graph import build_graph
from supabase import create_client
from dotenv import load_dotenv
import os
import uuid

load_dotenv()

app = FastAPI(title="DSStar Backend API", version="1.0")

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

graph = build_graph()

class TaskSubmission(BaseModel):
    query: str
    formatting_guidelines: str = ""

@app.get("/health", 
         summary="Health Check", 
         description="Check if the API is running", 
         tags=["System"])
async def health():
    return {"status": "ok"}


@app.post("/api/v1/submit_task", 
          summary="Submit Task", 
          description="Submit a new task for processing", 
          tags=["Tasks"])
async def submit_task(task: TaskSubmission):
    task_id = str(uuid.uuid4())

    supabase.table("tasks").insert({
        "task_id": task_id,
        "query": task.query,
        "formatting_guidelines": task.formatting_guidelines,
        "status": "running"
    }).execute()

        # Build initial state
    initial_state = {
        "task_id":               task_id,
        "query":                 task.query,
        "formatting_guidelines": task.formatting_guidelines,
        "data_descriptions":     {},
        "cumulative_plan":       [],
        "current_script":        "",
        "execution_result":      "",
        "exit_code":             0,
        "current_round":         0,
        "max_rounds":            10,
        "verifier_verdict":      "",
        "router_decision":       "",
        "status":                "running",
        "final_result":          None,
    }

    config = {"configurable": {"thread_id": task_id}}

    result = graph.invoke(initial_state, config=config)

    supabase.table("tasks").update({
        "status": result["status"],
        "final_result": result.get("final_result")
    }).eq("task_id", task_id).execute()

    return {"task_id": task_id, 
            "status": result["status"],
            "query": task.query,
            "rounds_taken": result["current_round"],
            "final_result": result["final_result"]}


@app.get("/api/v1/get_tasks", 
         summary="Get Tasks",   
         description="Retrieve a list of all tasks", 
         tags=["Tasks"])
async def get_tasks():
    response = supabase.table("tasks").select("*").order("created_at", desc=True).execute()
    return response.data


@app.get("/api/v1/get_task/{task_id}", 
         summary="Get Task", 
         description="Retrieve a specific task by its ID", 
         tags=["Tasks"])
async def get_task(task_id: str):
    response = supabase.table("tasks").select("*").eq("task_id", task_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Task not found")
    return response.data[0]
