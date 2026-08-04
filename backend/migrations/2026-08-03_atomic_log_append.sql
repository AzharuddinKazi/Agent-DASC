-- Closes a read-modify-write race in agents/logger.py's log_event(): it previously did
-- SELECT logs -> append in Python -> UPDATE the whole array, which drops an entry
-- whenever two log_event() calls for the same task_id interleave — a real scenario, not
-- theoretical: a user's Stop/Pause request runs on the main event loop while the graph's
-- currently-running node logs from run_graph's background thread (run_in_executor),
-- genuinely concurrently for the same task_id.
--
-- This function makes the append atomic at the database level — a single UPDATE using
-- jsonb concatenation, so there's no read-modify-write window in application code at all.
--
-- Applied directly against the live Supabase Postgres instance via SUPABASE_DB_URL (this
-- repo has no migration runner/tracked history yet — this file exists for documentation
-- and reproducibility, not automated application). Additive only — logger.py still has a
-- Python-side fallback for environments where this function doesn't exist yet. Safe to
-- drop if ever abandoned:
--   DROP FUNCTION IF EXISTS append_task_log;

CREATE OR REPLACE FUNCTION append_task_log(p_task_id text, p_entry jsonb)
RETURNS void
LANGUAGE sql
AS $$
  UPDATE tasks
  SET logs = COALESCE(logs, '[]'::jsonb) || jsonb_build_array(p_entry)
  WHERE task_id = p_task_id::uuid;
$$;
