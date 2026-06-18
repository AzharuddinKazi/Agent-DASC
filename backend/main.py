from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from agents.graph import build_graph
from supabase import create_client, Client
from dotenv import load_dotenv
import os, uuid, asyncio

load_dotenv()

supabase: Client = None
graph = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global supabase, graph
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))
    graph = build_graph()
    yield

app = FastAPI(title="DSStar Backend API", version="1.0", lifespan=lifespan)


class TaskSubmission(BaseModel):
    query: str
    formatting_guidelines: str = ""


async def run_graph(task_id: str, initial_state: dict):
    config = {"configurable": {"thread_id": task_id}}
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: graph.invoke(initial_state, config=config)
        )
        supabase.table("tasks").update({
            "status":       result["status"],
            "final_result": result.get("final_result"),
            "rounds_taken": result["current_round"],
        }).eq("task_id", task_id).execute()
    except Exception as e:
        supabase.table("tasks").update({
            "status": "failed", "final_result": str(e)
        }).eq("task_id", task_id).execute()


@app.get("/health", summary="Health Check", tags=["System"])
async def health():
    return {"status": "ok"}


@app.post("/api/v1/submit_task", summary="Submit Task", tags=["Tasks"], status_code=202)
async def submit_task(task: TaskSubmission, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())

    initial_state = {
        "task_id":               task_id,
        "query":                 task.query,
        "formatting_guidelines": task.formatting_guidelines,
        "data_descriptions":     {},
        "cumulative_plan":       [],
        "current_script":        "",
        "execution_result":      "",
        "exit_code":             0,
        "debug_attempts":        0,
        "current_round":         0,
        "max_rounds":            10,
        "verifier_verdict":      "",
        "router_decision":       "",
        "status":                "running",
        "final_result":          None,
    }

    supabase.table("tasks").insert({
        "task_id":               task_id,
        "query":                 task.query,
        "formatting_guidelines": task.formatting_guidelines,
        "status":                "running",
    }).execute()

    background_tasks.add_task(run_graph, task_id, initial_state)

    return {"task_id": task_id, "status": "running", "query": task.query}


@app.get("/api/v1/get_tasks", summary="Get Tasks", tags=["Tasks"])
async def get_tasks():
    response = supabase.table("tasks").select("*").order("created_at", desc=True).execute()
    return response.data


@app.get("/api/v1/get_task/{task_id}", summary="Get Task", tags=["Tasks"])
async def get_task(task_id: str):
    response = supabase.table("tasks").select("*").eq("task_id", task_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Task not found")
    return response.data[0]