import { describe, it, expect, vi, afterEach } from "vitest"
import { render, screen, fireEvent, cleanup } from "@testing-library/react"
import ErrorBoundary from "./ErrorBoundary"

function Bomb() {
  throw new Error("boom")
}

afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe("ErrorBoundary", () => {
  it("renders children when nothing throws", () => {
    render(<ErrorBoundary><div>fine</div></ErrorBoundary>)
    expect(screen.getByText("fine")).toBeInTheDocument()
  })

  it("catches a render error and shows a fallback instead of crashing the page", () => {
    vi.spyOn(console, "error").mockImplementation(() => {})
    render(<ErrorBoundary><Bomb /></ErrorBoundary>)
    expect(screen.getByText("Something went wrong")).toBeInTheDocument()
  })

  it("calls onReset when 'Try again' is clicked", () => {
    vi.spyOn(console, "error").mockImplementation(() => {})
    const onReset = vi.fn()
    render(<ErrorBoundary onReset={onReset}><Bomb /></ErrorBoundary>)

    fireEvent.click(screen.getByText("Try again"))
    expect(onReset).toHaveBeenCalledTimes(1)
  })
})
