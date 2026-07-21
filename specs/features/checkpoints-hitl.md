# Feature Spec: Checkpoints & Human-in-the-Loop (HITL)

## Purpose
Implements the four checkpoints that pause agent execution and wait for human input.
Built on LangGraph's interrupt/resume mechanism with PostgreSQL-backed persistence so
checkpoints survive browser refreshes, server restarts, and tab closures.

## Checkpoint Types [LOCKED — 5 types]

| Type | Fires after | Human action |
|---|---|---|
| `plan_approval` (CP1) | Planner_init generates first step | Approve → Coder runs · Reject+hint → Planner reruns. Also where DSSTAR+ mode auto-detection is shown and can be overridden (see `specs/agents/finalyzer.md`). |
| `force_exit` round 1 | `iteration >= max_iterations` (default 5) | Provide hint → 3 more iterations (iteration reset to `max_iterations - 3`) · Abandon → session failed |
| `force_exit` round 2 | `iteration >= max_iterations + 3` (default 8), still no "Yes" | **Abandon only, or Start Fresh Session** (pre-filled with accumulated hints + question). No further in-place hint round — caps the guided-retry mechanism at 2 rounds / 11 iterations total. |
| `result_confirmation` (CP2) | Verifier returns "Yes" | Approve → Finalyzer/SubquestionGenerator · Reject → same Abandon/Hint choice as force-exit; a hint routes back through Router and consumes one of the same 2 hint rounds |
| `refine_round_review` (new) | Writer_init completes, and after every Writer_refine round (DSSTAR+ only) | Refine further → another SubquestionGenerator_refine/DS-STAR/Writer_refine round · Finalize → proceeds to CP3. Replaces the old "3 automatic refine rounds" default. |
| `report_approval` (CP3) | Finalize chosen at `refine_round_review`, or Finalyzer completes (base mode) | Save · Export PDF · Share · Discard |

## LangGraph Implementation

### Checkpointer setup
```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

checkpointer = AsyncPostgresSaver.from_conn_string(
    os.environ["DATABASE_URL"]
)
graph = build_dsstar_graph().compile(
    checkpointer=checkpointer,
    interrupt_before=[
        "cp1_gate", "force_exit_gate", "cp2_gate",
        "refine_round_review_gate", "cp3_gate",
    ]
)
```
[LOCKED] `force_exit_gate` is a single gate node shared by both force-exit rounds — the
gate handler branches on `state["force_exit_round"]` to decide which payload/action set to
show (see Force-Exit Iteration Counter below).

Gate nodes are no-op nodes inserted before each checkpoint point. LangGraph interrupts BEFORE the gate node executes, pausing the thread.

### Graph state
```python
class DSStarState(TypedDict):
    # Core
    session_id:       str
    user_id:          str
    user_query:       str
    filenames:        list[str]
    summaries:        list[str]           # per-file, parallel to filenames

    # Planning
    plan:             list[str]           # accumulated step texts
    current_step:     str

    # Code
    base_code:        str                 # cumulative script
    execution_result: str                 # latest Docker stdout

    # Control
    iteration:         int
    max_iterations:    int                # default 5
    force_exit_round:  int                # 0 = not yet fired, 1 = first hint used, 2 = final (abandon/fresh-session only)
    hint:              str | None         # user hint from force_exit CP or CP2 reject

    # DSSTAR+
    mode:              Literal["base", "plus"]
    mode_source:       Literal["auto_detected", "human_override"]
    sub_questions:     list[str]
    sub_answers:       list[SubquestionAnswer]
    report_draft:      str | None
    refinement_round:  int                # 0 = init (Writer_init just ran), 1+ = each on-demand refine round, all human-triggered via refine_round_review
```

### Interrupt / resume flow
```python
# Start or resume a session
async def run_session(session_id: str, user_input: dict | None = None):
    config = {"configurable": {"thread_id": session_id}}

    if user_input:
        # Resume after checkpoint — inject human response into state
        await graph.aupdate_state(config, user_input)

    async for event in graph.astream(None, config, stream_mode="values"):
        # Stream events to WebSocket
        await ws_broadcast(session_id, event)
```

## Checkpoint Persistence (PostgreSQL)

Each checkpoint is recorded in the `checkpoints` table the moment the LangGraph thread is interrupted:

```python
async def on_interrupt(session_id: str, checkpoint_type: str, payload: dict):
    await db.execute("""
        INSERT INTO checkpoints (session_id, checkpoint_type, status, payload)
        VALUES ($1, $2, 'pending', $3)
    """, session_id, checkpoint_type, json.dumps(payload))

    # Update session status to 'waiting_for_checkpoint'
    await db.execute("""
        UPDATE analysis_sessions SET status = 'active', updated_at = NOW()
        WHERE id = $1
    """, session_id)
```

## Checkpoint Payloads

### plan_approval
```json
{
  "first_step": "Load the orders table and print the first 5 rows",
  "summaries_preview": "orders: 12 columns, ~2.1M rows. customers: 8 columns...",
  "detected_mode": "base",
  "mode_override": null
}
```

### force_exit (round 1)
```json
{
  "force_exit_round": 1,
  "iteration": 5,
  "max_iterations": 5,
  "last_result": "DataFrame with 0 rows returned",
  "verifier_verdict": "No",
  "plan_so_far": ["Step 1: ...", "Step 2: ..."],
  "available_actions": ["hint", "abandon"],
  "hint_instructions": "Provide additional context to help the agent continue"
}
```

### force_exit (round 2 — final)
```json
{
  "force_exit_round": 2,
  "iteration": 8,
  "max_iterations": 5,
  "last_result": "DataFrame with 0 rows returned",
  "verifier_verdict": "No",
  "plan_so_far": ["Step 1: ...", "Step 2: ...", "Step 3: ..."],
  "hints_so_far": ["Filter out cancelled orders before aggregating"],
  "available_actions": ["start_fresh_session", "abandon"]
}
```

### result_confirmation
```json
{
  "question": "What is the total revenue by product category for Q3 2024?",
  "plan": ["Step 1: Load orders...", "Step 2: Filter by date...", "Step 3: Aggregate..."],
  "result": "Electronics: $1.2M\nFurniture: $890K\nApparel: $654K",
  "code": "import pandas as pd\n...",
  "available_actions": ["approve", "hint", "abandon"]
}
```

### refine_round_review
```json
{
  "refinement_round": 0,
  "report_preview": "<h1>Customer Churn Analysis Q3 2024</h1><p>Executive Summary...",
  "sub_questions_answered": 6,
  "available_actions": ["refine_further", "finalize"]
}
```

### report_approval
```json
{
  "mode": "base",
  "preview": "Total revenue for Q3 2024 was $2.744M across 3 categories...",
  "report_title": null,
  "available_actions": ["save", "discard"]
}
```
or for DSSTAR+:
```json
{
  "mode": "plus",
  "preview": "<h1>Customer Churn Analysis Q3 2024</h1><p>Executive Summary...",
  "report_title": "Customer Churn Analysis — Q3 2024",
  "available_actions": ["save", "export_pdf", "share", "discard"]
}
```
Note: "refine" is no longer an action here — refinement now happens exclusively at the
`refine_round_review` checkpoint, before CP3 fires.

## API: Checkpoint Response Handling

```
POST /api/v1/analyses/{session_id}/checkpoint
Body: { "action": "approve" | "reject" | "hint" | "abandon" | "refine_further" | "finalize" | "start_fresh_session", "hint": "..." }
```

### Action routing [LOCKED]

| Checkpoint type | Valid actions | Behaviour |
|---|---|---|
| `plan_approval` | `approve`, `reject` (with hint) | approve → Resume → Coder_init · reject → Planner_init reruns with hint |
| `force_exit` round 1 | `hint`, `abandon` | hint → resume with hint injected, iteration reset to `max_iterations - 3`, `force_exit_round` → 1 · abandon → session failed |
| `force_exit` round 2 | `abandon`, `start_fresh_session` | abandon → session failed · start_fresh_session → new session created with accumulated hints + original question pre-filled |
| `result_confirmation` | `approve`, `hint`, `abandon` | approve → Finalyzer/SubquestionGenerator · hint → routes back through Router, consumes one of the 2 shared hint rounds · abandon → session failed |
| `refine_round_review` | `refine_further`, `finalize` | refine_further → another SubquestionGenerator_refine/DS-STAR/Writer_refine round, `refinement_round` += 1 · finalize → proceeds to CP3 |
| `report_approval` | `approve` (save), `abandon` (discard) | approve → session completed · abandon → session abandoned |

### Resume implementation [LOCKED]
```python
async def respond_to_checkpoint(session_id: str, action: str, hint: str | None):
    checkpoint = await get_pending_checkpoint(session_id)

    state_update = {}
    if action == "hint":
        # Valid for both force_exit round 1 and result_confirmation reject.
        # Both draw from the same shared 2-round hint budget.
        state_update["hint"] = hint
        state_update["iteration"] = checkpoint.payload["max_iterations"] - 3
        state_update["force_exit_round"] = checkpoint.payload.get("force_exit_round", 0) + 1
    elif action == "start_fresh_session":
        return await create_session(
            user_id=current_user_id,
            question=checkpoint.payload["question"],
            hints=checkpoint.payload.get("hints_so_far", []) + ([hint] if hint else []),
        )
    elif action == "refine_further":
        state_update["refinement_round"] = checkpoint.payload["refinement_round"] + 1
    elif action == "finalize":
        pass  # falls through to CP3 gate, no state change
    elif action == "approve" and checkpoint.type == "report_approval":
        await save_report(session_id)

    # Update checkpoint record
    await db.execute("""
        UPDATE checkpoints
        SET status = $1, user_hint = $2, responded_by = $3, responded_at = NOW()
        WHERE id = $4
    """, action_to_status(action), hint, current_user_id, checkpoint.id)

    # Resume LangGraph thread (skipped for start_fresh_session — that's a new thread)
    if action != "start_fresh_session":
        await run_session(session_id, user_input=state_update)
```

## WebSocket Events for Checkpoints

When a checkpoint fires, a `checkpoint_pending` event is broadcast:
```json
{
  "event": "checkpoint_pending",
  "data": {
    "checkpoint_type": "plan_approval",
    "checkpoint_id": "uuid",
    "payload": { ... }
  }
}
```

The frontend shows the checkpoint UI inline in the analysis session view.
When the human responds and agents resume, an `agent_started` event follows.

## Force-Exit: Iteration Counter [LOCKED — 2 hint rounds max, 11 iterations total]

```
Max iterations = 5 (configurable via DSSTAR_MAX_ITERATIONS env var)

Loop:
  iteration 1: Coder_init → Verifier → "No" → Router
  iteration 2: Coder_next/Planner_next → Verifier → "No" → Router
  iteration 3: ...
  iteration 4: ...
  iteration 5: BEFORE Verifier → fire force_exit checkpoint (round 1)
               → human provides hint (or abandons — session ends here if so)
               → iteration reset to 2 (5 - 3 = 2, giving 3 more tries)
               → force_exit_round = 1
  iteration 6: Coder_next (with hint in question context) → Verifier
  iteration 7: ...
  iteration 8: Verifier still "No" → fire force_exit checkpoint (round 2, FINAL)
               → only "abandon" or "start_fresh_session" offered — no third in-place hint
               → if start_fresh_session: new session created with both hints + question
                 pre-filled; this session marked "abandoned"
               → if abandon: session marked "failed"

  (If Verifier returns "Yes" at any point in this loop, proceed directly to CP2 —
   the walkthrough above shows the worst case where it never succeeds.)
```

Example success path: iteration 6 (post round-1 hint) → Verifier → "Yes" → CP2. The 11-
iteration ceiling is the worst case, not the expected case.

## Error Handling
| Error | Behaviour |
|---|---|
| LangGraph thread not found | 404 on checkpoint GET |
| Respond to checkpoint when none pending | 404 |
| Invalid action for checkpoint type | 400 with message "action 'hint' not valid for plan_approval" |
| Agent fails during resume | Session marked "failed", error stored in agent_steps |
| Server restart mid-session | LangGraph AsyncPostgresSaver restores thread state — session resumes from last checkpoint |

## Test Scenarios

### Unit
- `plan_approval` + approve → LangGraph thread resumes, Coder_init called
- `plan_approval` + reject → Planner_init reruns with hint (session stays active, not abandoned)
- `force_exit` round 1 + hint → iteration counter reset to `max_iterations - 3`, `force_exit_round` set to 1, hint injected into state
- `force_exit` round 1 + abandon → session status set to "failed"
- `force_exit` round 2 (force_exit_round == 1, still no "Yes") + `hint` action → rejected as invalid (only `abandon`/`start_fresh_session` valid at round 2)
- `force_exit` round 2 + `start_fresh_session` → new session created with accumulated hints, original session marked "abandoned"
- `result_confirmation` + `hint` → routes back through Router, consumes one of the 2 shared hint rounds (same counter as force_exit)
- `refine_round_review` + `refine_further` → `refinement_round` incremented, SubquestionGenerator_refine called
- `refine_round_review` + `finalize` → proceeds to CP3, no further sub-question generation
- Invalid action for checkpoint type → 400 response
- Server restart → thread state restored from PostgreSQL checkpointer

### Integration (real LangGraph + real DB)
- Full flow: POST /analyses → CP1 fires → approve → agents run → CP2 fires → approve → CP3 fires → save
- Force-exit fires at iteration 5 with correct payload
- Hint provided at force-exit → agents resume with hint in context → Verifier returns "Yes" within 3 tries
- WebSocket receives checkpoint_pending event at correct point in flow
- Browser refresh during active session → GET /analyses/{id} returns pending_checkpoint inline
