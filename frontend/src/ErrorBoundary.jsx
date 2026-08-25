import { Component } from "react"

// Cheap insurance against a blank white screen (or a raw React dev overlay) if a render
// throws — no dedicated error boundary existed anywhere in this app before. Deliberately
// minimal: this isn't trying to recover state, just to keep the tab showing something a
// non-technical viewer can act on instead of nothing.
export default class ErrorBoundary extends Component {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error, info) {
    console.error("Unhandled render error:", error, info)
  }

  render() {
    if (!this.state.hasError) return this.props.children
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-subtle px-4">
        <div className="max-w-sm text-center flex flex-col items-center gap-3">
          <h1 className="text-heading font-bold text-foreground">Something went wrong</h1>
          <p className="text-body text-muted-foreground">
            An unexpected error occurred. Refreshing the page usually fixes it.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium cursor-pointer"
          >
            Refresh
          </button>
        </div>
      </div>
    )
  }
}
