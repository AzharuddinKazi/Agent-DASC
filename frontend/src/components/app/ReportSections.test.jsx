import { describe, it, expect, afterEach } from "vitest"
import { render, screen, fireEvent, cleanup } from "@testing-library/react"
import ReportSections from "./ReportSections"

afterEach(() => cleanup())

function resultWithRows(count) {
  const rows = Array.from({ length: count }, (_, i) => [`Entity-${i}`, i])
  return JSON.stringify({
    summary: "Test summary.",
    key_findings: [],
    columns: ["entity", "value"],
    rows,
    chart: null,
    raw: "",
  })
}

describe("ReportSections results table pagination", () => {
  it("shows no pagination controls for a small result set", () => {
    render(<ReportSections result={resultWithRows(10)} script="" plan={[]} onFollowUp={() => {}} />)
    expect(screen.queryByLabelText("Next page")).not.toBeInTheDocument()
    expect(screen.getByText("Entity-0")).toBeInTheDocument()
  })

  it("paginates a large result set instead of rendering every row at once", () => {
    render(<ReportSections result={resultWithRows(120)} script="" plan={[]} onFollowUp={() => {}} />)

    expect(screen.getByText("Entity-0")).toBeInTheDocument()
    expect(screen.queryByText("Entity-99")).not.toBeInTheDocument()
    expect(screen.getByText("Page 1 of 3")).toBeInTheDocument()
    expect(screen.getByLabelText("Previous page")).toBeDisabled()
  })

  it("advances to the next page and shows rows beyond the first 50", () => {
    render(<ReportSections result={resultWithRows(120)} script="" plan={[]} onFollowUp={() => {}} />)

    fireEvent.click(screen.getByLabelText("Next page"))

    expect(screen.getByText("Page 2 of 3")).toBeInTheDocument()
    expect(screen.getByText("Entity-50")).toBeInTheDocument()
    expect(screen.queryByText("Entity-0")).not.toBeInTheDocument()
  })

  it("disables Next on the last page and re-enables Previous", () => {
    render(<ReportSections result={resultWithRows(120)} script="" plan={[]} onFollowUp={() => {}} />)

    fireEvent.click(screen.getByLabelText("Next page"))
    fireEvent.click(screen.getByLabelText("Next page"))

    expect(screen.getByText("Page 3 of 3")).toBeInTheDocument()
    expect(screen.getByLabelText("Next page")).toBeDisabled()
    expect(screen.getByLabelText("Previous page")).not.toBeDisabled()
    expect(screen.getByText("Entity-100")).toBeInTheDocument()
  })

  it("resets to page 1 when the column sort changes", () => {
    render(<ReportSections result={resultWithRows(120)} script="" plan={[]} onFollowUp={() => {}} />)

    fireEvent.click(screen.getByLabelText("Next page"))
    expect(screen.getByText("Page 2 of 3")).toBeInTheDocument()

    fireEvent.click(screen.getByText("entity"))
    expect(screen.getByText("Page 1 of 3")).toBeInTheDocument()
  })

  it("survives a re-render of a scalar-answer result with no rows/columns field", () => {
    // Regression test for a real crash caught live by ErrorBoundary: `parsed?.rows || []`
    // synthesizes a brand-new array every render when the result has no "rows" key at
    // all (e.g. this exact shape — a plain scalar answer, no table). The pagination
    // reset compares that fallback array by reference against the previous render's —
    // on mount they happen to be the same expression evaluated once (trivially equal),
    // but Dashboard polls every 2s and re-renders this component with a fresh task
    // object each time, which is exactly a second render with no *meaningful* prop
    // change. That's what a bare `rerender()` reproduces: a second render recomputes a
    // new empty array, mismatches the first's, calls setPage(0), which triggers a third
    // render that mismatches the second's, and so on — React throws "Too many
    // re-renders" after its render-phase-update cap. A stable EMPTY_ARRAY fallback
    // fixes it by making consecutive renders compare equal when nothing really changed.
    const result = JSON.stringify({
      summary: "There are 10000 outpatient claims.",
      key_findings: ["Total outpatient claims: 10000"],
    })
    const { rerender } = render(<ReportSections result={result} script="" plan={[]} onFollowUp={() => {}} />)
    rerender(<ReportSections result={result} script="" plan={[]} onFollowUp={() => {}} />)
    expect(screen.getByText("There are 10000 outpatient claims.")).toBeInTheDocument()
  })
})
