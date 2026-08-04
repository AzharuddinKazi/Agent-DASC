import { describe, it, expect, afterEach } from "vitest"
import { render, screen, cleanup } from "@testing-library/react"
import ReportPanel from "./ReportPanel"

afterEach(() => cleanup())

describe("ReportPanel completed-with-no-result state", () => {
  it("shows the results view when completed with a final_result", () => {
    const task = {
      status: "completed",
      task_type: "qa",
      final_result: JSON.stringify({ summary: "ok", key_findings: [], columns: [], rows: [] }),
    }
    render(<ReportPanel task={task} query="q" onFollowUp={() => {}} />)
    expect(screen.getByText("ok")).toBeInTheDocument()
  })

  it("shows an explicit terminal message instead of the loading UI when completed with no final_result", () => {
    // Regression test: a "completed" task with an empty/missing final_result used to
    // fall through to the loading/pipeline UI with nothing left polling to ever move it
    // forward — status is already terminal, so it was stuck there permanently.
    const task = { status: "completed", task_type: "qa", final_result: null, logs: [] }
    render(<ReportPanel task={task} query="q" onFollowUp={() => {}} />)

    expect(screen.getByText("Analysis Completed With No Result")).toBeInTheDocument()
    expect(screen.queryByPlaceholderText(/Steer the analysis/i)).not.toBeInTheDocument()
  })

  it("treats an empty-string final_result the same as missing", () => {
    const task = { status: "completed", task_type: "qa", final_result: "", logs: [] }
    render(<ReportPanel task={task} query="q" onFollowUp={() => {}} />)

    expect(screen.getByText("Analysis Completed With No Result")).toBeInTheDocument()
  })

  it("still shows the loading/pipeline UI for a running task", () => {
    const task = { status: "running", task_type: "qa", final_result: null, logs: [], cumulative_plan: [] }
    render(<ReportPanel task={task} query="q" onFollowUp={() => {}} />)

    expect(screen.getByPlaceholderText(/Steer the analysis/i)).toBeInTheDocument()
    expect(screen.queryByText("Analysis Completed With No Result")).not.toBeInTheDocument()
  })
})
