// Folds clarifying-question answers into the query text as an explicit context block —
// the pipeline only ever sees a single query string, so this is the one place answers
// can travel through submitTask into the actual analysis. Shared by EmptyState (initial
// submission) and Dashboard (QA/Report follow-up bar), the two places a query is submitted.
export function appendClarificationContext(query, resolvedAnswers) {
  if (!resolvedAnswers?.length) return query
  const lines = resolvedAnswers.map(r => `- ${r.question} → ${r.answer}`).join("\n")
  return `${query}\n\nAdditional context from clarifying questions:\n${lines}`
}
