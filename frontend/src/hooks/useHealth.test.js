import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { renderHook, act, cleanup } from "@testing-library/react"
import { useHealth } from "./useHealth"
import { checkHealth } from "../api"

vi.mock("../api", () => ({ checkHealth: vi.fn() }))

beforeEach(() => { vi.clearAllMocks(); vi.useFakeTimers() })
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks() })

describe("useHealth", () => {
  it("returns the polled health data once the request resolves", async () => {
    checkHealth.mockResolvedValue({ data: { status: "ok", checks: {} } })

    const { result } = renderHook(() => useHealth(30000))
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })

    expect(result.current.loading).toBe(false)
    expect(result.current.health).toEqual({ status: "ok", checks: {} })
  })

  it("degrades gracefully instead of throwing when the health check fails", async () => {
    checkHealth.mockRejectedValue(new Error("network down"))

    const { result } = renderHook(() => useHealth(30000))
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })

    expect(result.current.loading).toBe(false)
    expect(result.current.health).toEqual({ status: "degraded", checks: {} })
  })

  it("re-polls on the given interval", async () => {
    checkHealth.mockResolvedValue({ data: { status: "ok", checks: {} } })

    renderHook(() => useHealth(10000))
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    expect(checkHealth).toHaveBeenCalledTimes(1)

    await act(async () => { await vi.advanceTimersByTimeAsync(10000) })
    expect(checkHealth).toHaveBeenCalledTimes(2)
  })

  it("drops a late response and doesn't error after unmount", async () => {
    let resolveSecond
    checkHealth
      .mockResolvedValueOnce({ data: { status: "ok", checks: {} } })
      .mockImplementationOnce(() => new Promise(r => { resolveSecond = r }))

    const { result, unmount } = renderHook(() => useHealth(10000))
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    expect(checkHealth).toHaveBeenCalledTimes(1)

    await act(async () => { await vi.advanceTimersByTimeAsync(10000) })
    expect(checkHealth).toHaveBeenCalledTimes(2)

    unmount()
    // Resolving after unmount must not throw (a React "state update on unmounted
    // component" warning/error is exactly the failure mode the cancelled-flag guard
    // prevents) and must not be reflected anywhere observable.
    await act(async () => {
      resolveSecond({ data: { status: "degraded", checks: { db: "down" } } })
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(result.current.health).toEqual({ status: "ok", checks: {} })
  })
})
