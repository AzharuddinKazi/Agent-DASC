import { Component } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { AlertTriangle } from "lucide-react"

// Must be a class component — React only supports error boundaries via
// componentDidCatch/getDerivedStateFromError, there's no hook equivalent.
export default class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error("Unhandled render error:", error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="h-screen flex items-center justify-center bg-background p-6">
          <Card className="border-destructive/30 bg-destructive/5 max-w-md w-full">
            <CardContent className="p-6 flex flex-col items-center text-center gap-3">
              <AlertTriangle className="w-8 h-8 text-destructive" />
              <p className="text-body font-medium text-foreground">Something went wrong</p>
              <p className="text-caption text-muted-foreground">
                {this.props.message || "This section hit an unexpected error and couldn't render."}
              </p>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  this.setState({ error: null })
                  this.props.onReset?.()
                }}
              >
                Try again
              </Button>
            </CardContent>
          </Card>
        </div>
      )
    }
    return this.props.children
  }
}
