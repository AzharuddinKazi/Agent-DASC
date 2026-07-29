from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, BackgroundTasks, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import requests
import sentry_sdk
from agents.graph import build_graph
from agents.logger import log_event
from agents.query_clarity import generate_clarifying_questions
from agents.cancellation import request_stop, request_pause, clear as clear_cancellation, TaskCancelled, TaskPaused
from auth import get_current_user
from db import supabase
from observability import configure_logging, configure_error_tracking
import domain_pack
from domain_packs.catalog import get_pack, public_catalog
from knowledge import ingest_document
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from dotenv import load_dotenv
import logging, os, uuid, asyncio, io, zipfile, subprocess, time

load_dotenv()
configure_logging()
configure_error_tracking()
logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).parent

DOMAIN_PACK_README = """# {name} — Domain Pack

## What's in this zip
- `domain_pack_config.py` — a plain-Python export of this pack's current persona,
  classification, and sub-question dimensions, for reference or use outside this deployment.
- `generate_synthetic_data.py` — generates a matching example dataset into your `data/` folder.

Activation within this deployment doesn't require this zip — use the "Activate" button on
the Domain Packs page instead, which takes effect immediately with no restart.
"""

_DOMAIN_PACK_CONFIG_TEMPLATE = '''"""Exported domain pack config: {name} (pack_id={pack_id}).

Generated from this deployment's database at download time — for reference, or to
manually seed another deployment's domain_pack_configs table.
"""

REPORT_PERSONA = {report_persona!r}
REPORT_CLASSIFICATION = {report_classification!r}
SUBQUESTION_DIMENSIONS = {subquestion_dimensions!r}
'''

# Bounds how many pipeline runs (each spinning up 2GB-capped Docker sandbox containers at
# their Executor step) can actually execute at once. Without this, submit_task's implicit
# default ThreadPoolExecutor (sized min(32, cpu_count+4), nobody chose that number) lets
# unbounded concurrent runs pile up — traced concretely to Docker-daemon/host-memory
# exhaustion around 15-20 simultaneous analyses. Extra submissions above this limit still get
# an immediate 202 and queue, they just don't start executing until a slot frees up.
MAX_CONCURRENT_PIPELINES = int(os.getenv("MAX_CONCURRENT_PIPELINES", "10"))
_pipeline_semaphore = asyncio.Semaphore(MAX_CONCURRENT_PIPELINES)

graph = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-existing bug this fixes: the checkpointer used to be opened, set up, and closed
    # (via `async with ... as checkpointer:` exiting immediately after build_graph()) all
    # before the app ever started serving requests — and build_graph() was called with no
    # checkpointer argument at all, so it silently compiled without one either way.
    # Checkpointing (what Pause/Resume needs) was never actually functional. It has to
    # stay open for the app's whole lifetime instead, since graph.invoke() calls happen
    # continuously while the app serves requests, not just at startup.
    #
    # AsyncPostgresSaver's sync methods (used by the synchronous graph.invoke() this
    # codebase calls via run_in_executor) are supported specifically when called from a
    # different thread than the one holding the event loop — verified this is the
    # intended, safe usage pattern (see AsyncPostgresSaver.get_tuple's own thread check),
    # which matches run_in_executor's worker-thread execution exactly.
    global graph
    checkpointer_cm = AsyncPostgresSaver.from_conn_string(os.getenv("SUPABASE_DB_URL"))
    checkpointer = await checkpointer_cm.__aenter__()
    await checkpointer.setup()
    graph = build_graph(checkpointer=checkpointer)
    try:
        yield
    finally:
        await checkpointer_cm.__aexit__(None, None, None)

app = FastAPI(title="DSStar Backend API", version="1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:5174,http://127.0.0.1:5174"
    ).split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

class TaskSubmission(BaseModel):
    query: str
    formatting_guidelines: str = ""
    task_type: str = "qa"   # "qa" | "report"
    use_domain_knowledge: bool = True
    domain_pack_id: str | None = None   # pins a specific pack for this task; None = use whichever pack is globally active
    max_rounds: int = Field(default=3, ge=1, le=5)          # QA planning steps (paper default: 3)
    max_report_rounds: int = Field(default=2, ge=1, le=4)   # writer<->evaluator passes (DS-STAR+ only)


class TaskClarification(BaseModel):
    query: str
    task_type: str = "qa"
    domain_pack_id: str | None = None


async def run_graph(task_id: str, initial_state: dict | None):
    """`initial_state=None` is how a paused task resumes — see agents/cancellation.py's
    module docstring for why passing None with the same thread_id makes LangGraph's
    checkpointer replay from the last completed node rather than starting over."""
    config = {"configurable": {"thread_id": task_id}}
    try:
        if _pipeline_semaphore.locked():
            log_event(task_id, "system", "Queued — waiting for an available worker slot", "info")

        async with _pipeline_semaphore:
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
    except TaskCancelled:
        log_event(task_id, "system", "Stopped by user", "info")
        supabase.table("tasks").update({
            "status": "stopped", "final_result": "Stopped by user"
        }).eq("task_id", task_id).execute()
    except TaskPaused:
        # Nothing to persist to the checkpoint here — LangGraph already durably saved
        # the state as of the last node that completed before the interrupt, via the
        # checkpointer wired up in lifespan(). Resuming re-invokes with initial_state=None
        # and the same thread_id, which replays from exactly that point.
        log_event(task_id, "system", "Paused by user", "info")
        supabase.table("tasks").update({"status": "paused"}).eq("task_id", task_id).execute()
    except Exception as e:
        logger.exception(f"Task {task_id} failed")
        sentry_sdk.capture_exception(e)
        supabase.table("tasks").update({
            "status": "failed", "final_result": str(e)
        }).eq("task_id", task_id).execute()
    finally:
        clear_cancellation(task_id)


async def _timed_check(fn, timeout=3.0):
    start = time.time()
    try:
        await asyncio.wait_for(asyncio.to_thread(fn), timeout=timeout)
        return {"status": "ok", "latency_ms": int((time.time() - start) * 1000)}
    except Exception as e:
        return {"status": "error", "latency_ms": int((time.time() - start) * 1000), "detail": str(e)}


def _ping_database():
    supabase.table("tasks").select("task_id").limit(1).execute()


def _ping_docker():
    subprocess.run(["docker", "info"], capture_output=True, timeout=3, check=True)


def _ping_llm():
    resp = requests.get(
        f"{os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')}/key",
        headers={"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"},
        timeout=5,
    )
    resp.raise_for_status()


@app.get("/health", summary="Health Check", tags=["System"])
async def health(response: Response):
    database, docker, llm = await asyncio.gather(
        _timed_check(_ping_database),
        _timed_check(_ping_docker),
        _timed_check(_ping_llm),
    )
    checks = {"database": database, "docker": docker, "llm": llm}
    healthy = all(c["status"] == "ok" for c in checks.values())
    if not healthy:
        response.status_code = 503
    # asyncio.Semaphore has no public accessor for available permits — _value is the
    # standard way to introspect it, just for reporting here, never used to gate logic.
    active = MAX_CONCURRENT_PIPELINES - _pipeline_semaphore._value
    return {
        "status": "ok" if healthy else "degraded",
        "checks": checks,
        "concurrency": {"active": active, "max": MAX_CONCURRENT_PIPELINES},
    }


@app.post("/api/v1/clarify_task", summary="Get Clarifying Questions", tags=["Tasks"])
async def clarify_task(task: TaskClarification, user=Depends(get_current_user)):
    """Runs before submit_task, not as part of the graph — cheap (no Docker sandbox, one
    LLM completion, occasionally two on a malformed-output retry) so the frontend can show
    a popup and block submission on the answer without a queueing/polling dance. Returns
    an empty list when the query doesn't need clarification, the common case, so the
    frontend skips the popup entirely.

    generate_clarifying_questions() calls the LLM via requests (synchronous/blocking) —
    run via run_in_executor, same as run_graph()'s graph.invoke() below, so this doesn't
    block the single asyncio event loop for the whole server for the ~2-10s round-trip.
    An `async def` route that calls blocking I/O directly freezes every other in-flight
    request (health checks, other users' task polling, everything) for that duration —
    exactly what a raw synchronous call here would do without this.
    """
    task_type = task.task_type if task.task_type in ("qa", "report") else "qa"
    questions = await asyncio.get_event_loop().run_in_executor(
        None, generate_clarifying_questions, task.query, task_type, task.domain_pack_id
    )
    return {"questions": questions}


@app.post("/api/v1/submit_task", summary="Submit Task", tags=["Tasks"], status_code=202)
async def submit_task(task: TaskSubmission, background_tasks: BackgroundTasks, user=Depends(get_current_user)):
    task_id   = str(uuid.uuid4())
    task_type = task.task_type if task.task_type in ("qa", "report") else "qa"

    domain_pack_id = task.domain_pack_id
    if domain_pack_id and domain_pack_id != "generic" and not get_pack(domain_pack_id):
        raise HTTPException(status_code=404, detail="Domain pack not found")

    initial_state = {
        "task_id":               task_id,
        "query":                 task.query,
        "formatting_guidelines": task.formatting_guidelines,
        "task_type":             task_type,
        "use_domain_knowledge":  task.use_domain_knowledge,
        "domain_pack_id":        domain_pack_id,
        # QA pipeline
        "data_descriptions":     {},
        "cumulative_plan":       [],
        "current_script":        "",
        "execution_result":      "",
        "exit_code":             0,
        "debug_attempts":        0,
        "current_round":         0,
        "max_rounds":            task.max_rounds,   # paper §3 default: max 3 sequential planning steps
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
        "max_report_rounds":     task.max_report_rounds,   # writer→evaluator passes before forcing finalizer
    }

    supabase.table("tasks").insert({
        "task_id":               task_id,
        "query":                 task.query,
        "formatting_guidelines": task.formatting_guidelines,
        "task_type":             task_type,
        "status":                "running",
        "user_id":               user.id,
    }).execute()

    background_tasks.add_task(run_graph, task_id, initial_state)

    return {
        "task_id":              task_id,
        "status":               "running",
        "query":                task.query,
        "task_type":            task_type,
        "use_domain_knowledge": task.use_domain_knowledge,
        "domain_pack_id":       domain_pack_id,
        "max_rounds":           task.max_rounds,
        "max_report_rounds":    task.max_report_rounds,
    }


@app.get("/api/v1/get_tasks", summary="Get Tasks", tags=["Tasks"])
async def get_tasks(user=Depends(get_current_user)):
    response = supabase.table("tasks").select("*").eq("user_id", user.id).order("created_at", desc=True).execute()
    return response.data


@app.get("/api/v1/get_task/{task_id}", summary="Get Task", tags=["Tasks"])
async def get_task(task_id: str, user=Depends(get_current_user)):
    import json as _json
    response = supabase.table("tasks").select("*").eq("task_id", task_id).eq("user_id", user.id).execute()
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


@app.post("/api/v1/tasks/{task_id}/stop", summary="Stop Task", tags=["Tasks"])
async def stop_task(task_id: str, user=Depends(get_current_user)):
    """Cooperative cancellation — see agents/cancellation.py for why this can't be an
    instant kill. Takes effect at the next graph-node boundary (seconds, for the common
    case of an LLM-call node) or, for a Docker execution in progress, within
    executor.POLL_INTERVAL_S (well under a second) since execute_script polls the same
    flag and kills the container directly rather than waiting out its own node boundary.
    """
    response = supabase.table("tasks").select("status").eq("task_id", task_id).eq("user_id", user.id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Task not found")
    if response.data[0]["status"] != "running":
        raise HTTPException(status_code=409, detail="Task is not running")

    request_stop(task_id)
    log_event(task_id, "system", "Stop requested — halting at the next safe point", "info")
    return {"task_id": task_id, "status": "stopping"}


@app.post("/api/v1/tasks/{task_id}/pause", summary="Pause Task", tags=["Tasks"])
async def pause_task(task_id: str, user=Depends(get_current_user)):
    """Same cooperative-interrupt mechanism as Stop (see stop_task above and
    agents/cancellation.py), but resumable: the step that was interrupted gets re-run
    from scratch on Resume rather than the task ending permanently."""
    response = supabase.table("tasks").select("status").eq("task_id", task_id).eq("user_id", user.id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Task not found")
    if response.data[0]["status"] != "running":
        raise HTTPException(status_code=409, detail="Task is not running")

    request_pause(task_id)
    log_event(task_id, "system", "Pause requested — halting at the next safe point", "info")
    return {"task_id": task_id, "status": "pausing"}


@app.post("/api/v1/tasks/{task_id}/resume", summary="Resume Task", tags=["Tasks"])
async def resume_task(task_id: str, background_tasks: BackgroundTasks, user=Depends(get_current_user)):
    response = supabase.table("tasks").select("status").eq("task_id", task_id).eq("user_id", user.id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Task not found")
    if response.data[0]["status"] != "paused":
        raise HTTPException(status_code=409, detail="Task is not paused")

    supabase.table("tasks").update({"status": "running"}).eq("task_id", task_id).execute()
    log_event(task_id, "system", "Resumed by user", "info")
    # initial_state=None is the resume signal — see run_graph's docstring.
    background_tasks.add_task(run_graph, task_id, None)
    return {"task_id": task_id, "status": "running"}


@app.get("/api/v1/domain_packs", summary="List Domain Packs", tags=["Domain Packs"])
async def list_domain_packs():
    active_id = domain_pack.get_active_pack_config()["pack_id"]
    return [
        {**pack, "active": pack["id"] == active_id}
        for pack in public_catalog()
    ]


@app.post("/api/v1/domain_packs/{pack_id}/activate", summary="Activate Domain Pack", tags=["Domain Packs"])
async def activate_domain_pack(pack_id: str, user=Depends(get_current_user)):
    if pack_id != "generic" and not get_pack(pack_id):
        raise HTTPException(status_code=404, detail="Domain pack not found")
    supabase.table("app_settings").upsert({"key": "active_domain_pack", "value": pack_id}).execute()
    return {"active": pack_id}


@app.post("/api/v1/domain_packs/deactivate", summary="Deactivate Domain Pack", tags=["Domain Packs"])
async def deactivate_domain_pack(user=Depends(get_current_user)):
    """Reverts the globally active pack to "generic". Equivalent to activating "generic"
    directly — exists as its own route so "turn domain knowledge off" doesn't require a
    caller to know the magic id "generic" is what that means."""
    supabase.table("app_settings").upsert({"key": "active_domain_pack", "value": "generic"}).execute()
    return {"active": "generic"}


@app.get("/api/v1/domain_packs/{pack_id}/download", summary="Download Domain Pack", tags=["Domain Packs"])
async def download_domain_pack(pack_id: str):
    pack = get_pack(pack_id)
    if not pack:
        raise HTTPException(status_code=404, detail="Domain pack not found")

    config_row = supabase.table("domain_pack_configs").select("*").eq("pack_id", pack_id).execute()
    if not config_row.data:
        raise HTTPException(status_code=404, detail="Domain pack config not found")
    cfg = config_row.data[0]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("domain_pack_config.py", _DOMAIN_PACK_CONFIG_TEMPLATE.format(
            name=pack["name"],
            pack_id=pack_id,
            report_persona=cfg["report_persona"],
            report_classification=cfg["report_classification"],
            subquestion_dimensions=cfg["subquestion_dimensions"] or [],
        ))
        if pack.get("dataset_generator"):
            zf.write(BACKEND_DIR / pack["dataset_generator"], "generate_synthetic_data.py")
        zf.writestr("README.md", DOMAIN_PACK_README.format(name=pack["name"]))
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{pack_id}-domain-pack.zip"'},
    )


@app.post("/api/v1/domain_packs/{pack_id}/documents", summary="Upload Knowledge Document", tags=["Domain Packs"])
async def upload_domain_pack_document(pack_id: str, file: UploadFile, background_tasks: BackgroundTasks, user=Depends(get_current_user)):
    if not get_pack(pack_id):
        raise HTTPException(status_code=404, detail="Domain pack not found")

    raw_bytes = await file.read()
    document_id = str(uuid.uuid4())
    supabase.table("domain_pack_documents").insert({
        "id":          document_id,
        "pack_id":     pack_id,
        "filename":    file.filename,
        "status":      "processing",
        "uploaded_by": user.id,
    }).execute()

    background_tasks.add_task(ingest_document, pack_id, document_id, file.filename, raw_bytes)

    return {"id": document_id, "filename": file.filename, "status": "processing"}


@app.get("/api/v1/domain_packs/{pack_id}/documents", summary="List Knowledge Documents", tags=["Domain Packs"])
async def list_domain_pack_documents(pack_id: str, user=Depends(get_current_user)):
    if not get_pack(pack_id):
        raise HTTPException(status_code=404, detail="Domain pack not found")
    response = (
        supabase.table("domain_pack_documents")
        .select("id, filename, status, error, chunk_count, created_at")
        .eq("pack_id", pack_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data


@app.delete("/api/v1/domain_packs/{pack_id}/documents/{doc_id}", summary="Delete Knowledge Document", tags=["Domain Packs"])
async def delete_domain_pack_document(pack_id: str, doc_id: str, user=Depends(get_current_user)):
    supabase.table("domain_pack_documents").delete().eq("id", doc_id).eq("pack_id", pack_id).execute()
    return {"status": "deleted"}