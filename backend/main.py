from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agents.graph import build_graph
# from supabase import create_client, Client
from db import supabase
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from dotenv import load_dotenv
import os, uuid, asyncio

load_dotenv()

# supabase: Client = None
graph = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global supabase, graph
    # supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))
    async with AsyncPostgresSaver.from_conn_string(os.getenv("SUPABASE_DB_URL")) as checkpointer:
        await checkpointer.setup()
        graph = build_graph()
    yield

app = FastAPI(title="DSStar Backend API", version="1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class TaskSubmission(BaseModel):
    query: str
    formatting_guidelines: str = ""
    task_type: str = "qa"   # "qa" | "report"


async def run_graph(task_id: str, initial_state: dict):
    config = {"configurable": {"thread_id": task_id}}
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: graph.invoke(initial_state, config=config)
        )
        import json as _json
        supabase.table("tasks").update({
            "status":       result["status"],
            "final_result": result.get("final_result"),
            "rounds_taken": result.get("current_round", 0),
            "current_script": result.get("current_script"),
            "task_type":    result.get("task_type", "qa"),
            "sub_results":  _json.dumps(result.get("sub_results") or {}),
        }).eq("task_id", task_id).execute()
    except Exception as e:
        import traceback
        print(f"[Error] Task {task_id} failed: {traceback.format_exc()}")
        supabase.table("tasks").update({
            "status": "failed", "final_result": str(e)
        }).eq("task_id", task_id).execute()


@app.get("/health", summary="Health Check", tags=["System"])
async def health():
    return {"status": "ok"}


@app.post("/api/v1/submit_task", summary="Submit Task", tags=["Tasks"], status_code=202)
async def submit_task(task: TaskSubmission, background_tasks: BackgroundTasks):
    task_id   = str(uuid.uuid4())
    task_type = task.task_type if task.task_type in ("qa", "report") else "qa"

    initial_state = {
        "task_id":               task_id,
        "query":                 task.query,
        "formatting_guidelines": task.formatting_guidelines,
        "task_type":             task_type,
        # QA pipeline
        "data_descriptions":     {},
        "cumulative_plan":       [],
        "current_script":        "",
        "execution_result":      "",
        "exit_code":             0,
        "debug_attempts":        0,
        "current_round":         0,
        "max_rounds":            3,   # paper §3: max 3 sequential planning steps
        "verifier_verdict":      "",
        "router_decision":       "",
        "status":                "running",
        "final_result":          None,
        # Report pipeline
        "sub_questions":         [],
        "current_sub_idx":       0,
        "sub_results":           {},
        "draft_report":          "",
        "report_verdict":        "",
        "report_gaps":           [],
        "report_rounds":         0,
        "max_report_rounds":     1,   # one writer→evaluator pass; gaps add sub-Qs if needed
    }

    supabase.table("tasks").insert({
        "task_id":               task_id,
        "query":                 task.query,
        "formatting_guidelines": task.formatting_guidelines,
        "task_type":             task_type,
        "status":                "running",
    }).execute()

    background_tasks.add_task(run_graph, task_id, initial_state)

    return {"task_id": task_id, "status": "running", "query": task.query, "task_type": task_type}


@app.get("/api/v1/get_tasks", summary="Get Tasks", tags=["Tasks"])
async def get_tasks():
    response = supabase.table("tasks").select("*").order("created_at", desc=True).execute()
    return response.data


@app.get("/api/v1/get_task/{task_id}", summary="Get Task", tags=["Tasks"])
async def get_task(task_id: str):
    import json as _json
    response = supabase.table("tasks").select("*").eq("task_id", task_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Task not found")
    row = response.data[0]
    if isinstance(row.get("sub_results"), str):
        try:
            row["sub_results"] = _json.loads(row["sub_results"])
        except Exception:
            row["sub_results"] = {}
    if isinstance(row.get("logs"), str):
        try:
            row["logs"] = _json.loads(row["logs"])
        except Exception:
            row["logs"] = []
    return row