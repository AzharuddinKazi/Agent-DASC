import { Card, CardContent } from "@/components/ui/card"

export function QueryCard({ query, label = "Query" }) {
  return (
    <Card>
      <CardContent className="py-4">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-1.5">{label}</p>
        <p className="text-sm font-medium text-foreground leading-relaxed">{query}</p>
      </CardContent>
    </Card>
  )
}

const MAX_ROUNDS = 3 // matches backend main.py initial_state.max_rounds for QA tasks

export function RoundBudgetCard({ currentRound = 0 }) {
  const pct = Math.min(100, Math.round((currentRound / MAX_ROUNDS) * 100))

  return (
    <Card>
      <CardContent className="py-4">
        <div className="flex items-center justify-between gap-6">
          <div>
            <p className="text-[11px] text-muted-foreground mb-1">Current Round</p>
            <p className="text-2xl font-bold text-foreground leading-none">{currentRound}</p>
            <p className="text-[11px] text-muted-foreground mt-1">of {MAX_ROUNDS} default</p>
          </div>
          <div>
            <p className="text-[11px] text-muted-foreground mb-1">Round Budget</p>
            <p className="text-2xl font-bold text-foreground leading-none">{currentRound} / {MAX_ROUNDS}</p>
            <p className="text-[11px] text-muted-foreground mt-1">rounds used</p>
          </div>
          <div className="flex-1 min-w-[120px]">
            <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
              <div className="h-full bg-foreground rounded-full transition-all duration-700" style={{ width: `${pct}%` }} />
            </div>
            <p className="text-[11px] text-muted-foreground mt-1.5 text-right">{Math.max(0, MAX_ROUNDS - currentRound)} remaining</p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default function PipelineHeader({ query, currentRound = 0, isReport }) {
  return (
    <div className="flex flex-col gap-4">
      <QueryCard query={query} label={isReport ? "Research Query" : "Query"} />
      {!isReport && <RoundBudgetCard currentRound={currentRound} />}
    </div>
  )
}
