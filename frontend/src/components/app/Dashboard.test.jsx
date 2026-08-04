import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, act, fireEvent, cleanup } from "@testing-library/react"
import Dashboard from "./Dashboard"
import { getTask } from "../../api"

vi.mock("../../api", () => ({
  getTask: vi.fn(),
  submitTask: vi.fn(),
  clarifyTask: vi.fn(),
  stopTask: vi.fn(),
  pauseTask: vi.fn(),
  resumeTask: vi.fn(),
  submitReviewDecision: vi.fn(),
}))

// Dashboard's own polling effect is what's under test here — the child components
// (Sidebar's task list, ReportPanel's rendering) are irrelevant to the stale-response
// race and pull in auth/health hooks and shadcn primitives that add noise, not signal.
// Sidebar's mock exposes a button that drives the real onSelect callback, the same one
// a real task-switch click in the sidebar would call — that's what actually flips
// Dashboard's internal activeTaskId state (the taskId prop is only the initial value).
vi.mock("./Sidebar", () => ({
  default: ({ onSelect }) => (
    <button data-testid="select-task-b" onClick={() => onSelect("task-b", "task b", "qa")} />
  ),
}))
vi.mock("./ReportPanel", () => ({
  default: ({ task }) => <div data-testid="report-panel">{task?.query ?? "no-task"}</div>,
}))
vi.mock("./ClarifyingQuestionsModal", () => ({ default: () => null }))

beforeEach(() => { vi.clearAllMocks(); vi.useFakeTimers({ shouldAdvanceTime: true }) })
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks() })

describe("Dashboard polling", () => {
  it("renders the task once the poll resolves", async () => {
    getTask.mockResolvedValue({ data: { task_id: "t1", query: "task one", status: "completed" } })

    render(<Dashboard taskId="t1" query="task one" />)

    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    expect(screen.getByTestId("report-panel").textContent).toBe("task one")
  })

  it("drops a stale response for a task the user has since switched away from", async () => {
    // Task A's fetch is slow and won't resolve until we manually flip the switch below;
    // task B's fetch resolves immediately once selected via the sidebar.
    let resolveTaskA
    getTask.mockImplementation((id) => {
      if (id === "task-a") return new Promise(r => { resolveTaskA = r })
      return Promise.resolve({ data: { task_id: id, query: "task b", status: "completed" } })
    })

    render(<Dashboard taskId="task-a" query="task a" />)
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    expect(screen.getByTestId("report-panel").textContent).toBe("no-task")

    fireEvent.click(screen.getByTestId("select-task-b"))
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    expect(screen.getByTestId("report-panel").textContent).toBe("task b")

    // Task A's slow response finally lands after the switch — it must not overwrite
    // the now-selected task B.
    await act(async () => {
      resolveTaskA({ data: { task_id: "task-a", query: "task a", status: "completed" } })
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(screen.getByTestId("report-panel").textContent).toBe("task b")
  })
})
