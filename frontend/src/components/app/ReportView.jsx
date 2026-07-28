import { useState, useMemo, useRef } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { ChevronRight, ChevronDown, Send, FileText, Database, CheckCircle2, Download, AlertTriangle, ShieldAlert } from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts"

const CHART_COLORS = [
  "var(--color-chart-1)", "var(--color-chart-2)", "var(--color-chart-3)",
  "var(--color-chart-4)", "var(--color-chart-5)", "var(--color-info)",
]
const TICK_STYLE  = { fontSize: 11, fill: "var(--color-muted-foreground)", fontFamily: "var(--font-sans)" }
const TIP_STYLE   = { fontSize: 12, border: "1px solid var(--color-border)", borderRadius: 6, boxShadow: "0 2px 8px rgba(0,0,0,.06)" }

const RISK_COLORS = {
  High:   "text-destructive bg-destructive/10 border-destructive/30",
  Medium: "text-amber-600 bg-amber-50 border-amber-200",
  Low:    "text-success bg-success/10 border-success/20",
}

// Writer emits inline citations as bracketed analysis numbers, e.g. "...8.3% [2]." or
// "...across regions [1,4]." — turn those into real markdown links to #source-N so both
// CitationLink (markdown bodies) and CitedText (plain-text fields) can render/scroll to them.
function linkifyCitations(text) {
  if (!text) return text
  return text.replace(/\[(\d+(?:\s*,\s*\d+)*)\]/g, (_, nums) =>
    nums.split(",").map(n => `[${n.trim()}](#source-${n.trim()})`).join("")
  )
}

function CitationLink({ href, children }) {
  if (href?.startsWith("#source-")) {
    return (
      <a href={href} className="inline-flex items-center justify-center text-label font-bold text-primary hover:underline align-super ml-0.5">
        [{children}]
      </a>
    )
  }
  return <a href={href} className="text-primary hover:underline" target="_blank" rel="noreferrer">{children}</a>
}

function ReportProse({ text }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: ({ children }) => <h1 className="text-lg font-bold text-foreground mt-6 mb-3 first:mt-0">{children}</h1>,
        h2: ({ children }) => <h2 className="text-base font-bold text-foreground mt-5 mb-2">{children}</h2>,
        h3: ({ children }) => <h3 className="text-sm font-semibold text-foreground mt-4 mb-1.5">{children}</h3>,
        p:  ({ children }) => <p className="text-sm text-foreground/80 leading-relaxed mb-3">{children}</p>,
        ul: ({ children }) => <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal pl-5 mb-3 space-y-1">{children}</ol>,
        li: ({ children }) => <li className="text-sm text-foreground/80 leading-relaxed">{children}</li>,
        strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
        code: ({ children }) => <code className="text-caption font-mono bg-muted px-1 py-0.5 rounded text-foreground">{children}</code>,
        blockquote: ({ children }) => (
          <blockquote className="border-l-4 border-border pl-4 my-3 text-muted-foreground italic text-sm">{children}</blockquote>
        ),
        table: ({ children }) => (
          <div className="overflow-x-auto my-4">
            <table className="w-full text-sm border-collapse border border-border rounded-lg overflow-hidden">{children}</table>
          </div>
        ),
        thead: ({ children }) => <thead className="bg-muted/50">{children}</thead>,
        th: ({ children }) => <th className="px-3 py-2 text-left text-xs font-bold uppercase tracking-wider text-muted-foreground border-b border-border">{children}</th>,
        td: ({ children }) => <td className="px-3 py-2 text-sm text-foreground/80 border-b border-border/50">{children}</td>,
        a: CitationLink,
      }}
    >
      {linkifyCitations(text)}
    </ReactMarkdown>
  )
}

// For plain-text fields (executive_summary, conclusions) that aren't markdown-rendered —
// same [N] citation syntax, same #source-N targets, no markdown parsing needed.
function CitedText({ text, className }) {
  if (!text) return null
  const parts = text.split(/\[(\d+(?:\s*,\s*\d+)*)\]/g)
  return (
    <p className={className}>
      {parts.map((part, i) => {
        if (i % 2 === 0) return <span key={i}>{part}</span>
        return part.split(",").map(n => (
          <a key={n} href={`#source-${n.trim()}`} className="text-label font-bold underline decoration-dotted underline-offset-2 hover:opacity-70 align-super ml-0.5">
            [{n.trim()}]
          </a>
        ))
      })}
    </p>
  )
}

function MiniChart({ rows, columns }) {
  if (!rows?.length || !columns || columns.length < 2) return null
  const data = rows.slice(0, 8).map(r => {
    const obj = {}
    columns.forEach((c, i) => { obj[c] = r[i] })
    return obj
  })
  const xKey = columns[0]
  const yKey = columns.find((c, i) => i > 0 && !isNaN(parseFloat(String(data[0]?.[c])))) || columns[1]
  if (!yKey || yKey === xKey) return null
  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
        <XAxis type="number" tick={TICK_STYLE} />
        <YAxis dataKey={xKey} type="category" tick={TICK_STYLE} width={120} />
        <Tooltip contentStyle={TIP_STYLE} />
        <Bar dataKey={yKey} radius={[0, 3, 3, 0]}>
          {data.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

function RiskBadge({ level }) {
  return (
    <span className={`text-label font-bold px-2 py-0.5 rounded border ${RISK_COLORS[level] || "text-muted-foreground bg-muted border-border"}`}>
      {level || "—"}
    </span>
  )
}

export default function ReportView({ task, query, onFollowUp }) {
  const [openSections, setOpenSections] = useState({ 0: true })
  const [followUpText, setFollowUpText] = useState("")
  const [followUpMode, setFollowUpMode] = useState("report")

  const toggleSection = key => setOpenSections(s => ({ ...s, [key]: !s[key] }))

  // Citation links (#source-N) point into the "Underlying Sub-analysis Data" section,
  // which may be collapsed — the target id doesn't exist in the DOM until it's open, so a
  // plain anchor jump silently does nothing. Intercept the click, force it open, then scroll
  // once React has rendered the now-expanded content.
  const handleCitationClick = e => {
    const link = e.target.closest('a[href^="#source-"]')
    if (!link) return
    e.preventDefault()
    setOpenSections(s => ({ ...s, sub_data: true }))
    const id = link.getAttribute("href").slice(1)
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "center" })
      })
    })
  }

  const report = useMemo(() => {
    const raw = task?.final_result
    if (!raw) return null
    try {
      let s = typeof raw === "string" ? raw.trim() : JSON.stringify(raw)
      if (s.startsWith("```")) s = s.replace(/^```[a-z]*\n?/, "").replace(/```$/, "").trim()
      return JSON.parse(s)
    } catch { return null }
  }, [task?.final_result])

  // Numbered, ordered source list backing the [N] citations — from report.sources when the
  // backend provided one (writer.py always attaches this now). Falls back to iterating
  // task.sub_results for reports generated before this change; that order isn't guaranteed
  // (JSONB doesn't preserve key order), so old reports' citation numbers may not line up
  // with this fallback numbering — acceptable since those reports have no [N] markers to
  // match against anyway.
  const citableSources = useMemo(() => {
    if (report?.sources?.length) return report.sources
    return Object.keys(task?.sub_results || {}).map((q, i) => ({ id: i + 1, question: q }))
  }, [report, task?.sub_results])

  const handleSubmit = e => {
    e.preventDefault()
    if (!followUpText.trim()) return
    onFollowUp(followUpText, followUpMode)
    setFollowUpText("")
  }

  if (!report) {
    return (
      <Card className="border-destructive/30 bg-destructive/5 max-w-2xl mx-auto mt-6">
        <CardContent className="p-5">
          <p className="text-sm text-destructive">Report could not be parsed. Raw output:</p>
          <pre className="text-xs text-muted-foreground mt-3 whitespace-pre-wrap font-mono">{task?.final_result}</pre>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="flex flex-col gap-5 pb-24 w-full" onClick={handleCitationClick}>

      {/* ── Report header ── */}
      <div className="flex items-start justify-between gap-4 print:hidden">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
            <Badge variant="secondary" className="text-label font-bold uppercase tracking-wider">DS-STAR+ Report</Badge>
            {report.classification && (
              <Badge variant="outline" className="text-label font-bold text-destructive border-destructive/30">
                {report.classification}
              </Badge>
            )}
          </div>
          <h1 className="text-xl font-bold text-foreground leading-tight">{report.title || query}</h1>
          {report.reporting_period && (
            <p className="text-xs text-muted-foreground mt-1">{report.reporting_period}</p>
          )}
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {report.data_coverage && (
            <div className="flex items-center gap-4 text-right">
              <div>
                <p className="text-xs text-muted-foreground">Sub-analyses</p>
                <p className="text-lg font-bold text-foreground">{report.data_coverage.sub_questions_answered}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Records</p>
                <p className="text-lg font-bold text-foreground">{(report.data_coverage.total_records_analysed || 0).toLocaleString()}</p>
              </div>
            </div>
          )}
          <Button variant="outline" size="sm" onClick={() => window.print()} className="gap-1.5 h-8 text-caption">
            <Download className="w-3 h-3" />
            Export PDF
          </Button>
        </div>
      </div>

      {/* ── Executive summary ── */}
      <Card className="border-foreground/10 bg-foreground text-background">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold text-background/90 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4" />
            Executive Summary
          </CardTitle>
        </CardHeader>
        <CardContent>
          <CitedText text={report.executive_summary} className="text-sm text-background/80 leading-relaxed" />
        </CardContent>
      </Card>

      {/* ── Report sections ── */}
      {(report.sections || []).map((section, i) => (
        <Card key={i}>
          <button
            onClick={() => toggleSection(i)}
            className="w-full flex items-center justify-between px-5 py-4 hover:bg-muted/30 transition-colors cursor-pointer rounded-t-lg text-left"
          >
            <div className="flex items-center gap-3">
              <div className="w-6 h-6 rounded-full bg-foreground flex items-center justify-center shrink-0">
                <span className="text-label font-bold text-background">{i + 1}</span>
              </div>
              <div>
                <p className="text-sm font-semibold text-foreground">{section.heading}</p>
                {section.key_stat && (
                  <CitedText text={section.key_stat} className="text-xs tabular-nums text-muted-foreground mt-0.5" />
                )}
              </div>
            </div>
            {openSections[i]
              ? <ChevronDown className="w-4 h-4 text-muted-foreground shrink-0" />
              : <ChevronRight className="w-4 h-4 text-muted-foreground shrink-0" />}
          </button>
          {openSections[i] && (
            <>
              <Separator />
              <CardContent className="pt-4 pb-5">
                <ReportProse text={section.body} />
              </CardContent>
            </>
          )}
        </Card>
      ))}

      {/* ── Risk matrix ── */}
      {/* Dimension names come from the Writer's own output (report.risk_matrix[].dimensions),
          not a hardcoded schema — this table adapts to whatever dimensions the LLM picked
          for this query's domain. Falls back to the pre-domain-pack flat fraud_risk/
          compliance_risk/operational_risk shape for reports generated before this change. */}
      {report.risk_matrix?.length > 0 && (() => {
        const rows = report.risk_matrix.map(row => ({
          ...row,
          dimensions: row.dimensions || {
            "Fraud Risk":      row.fraud_risk,
            "Compliance Risk": row.compliance_risk,
            "Operational Risk": row.operational_risk,
          },
        }))
        const dimensionNames = [...new Set(rows.flatMap(r => Object.keys(r.dimensions).filter(k => r.dimensions[k] != null)))]

        return (
          <Card>
            <button
              onClick={() => toggleSection("risk_matrix")}
              className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-muted/30 transition-colors cursor-pointer rounded-lg text-left"
            >
              <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <AlertTriangle className="w-4 h-4 text-amber-500" />
                Entity Risk Matrix
              </span>
              {openSections["risk_matrix"]
                ? <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
                : <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />}
            </button>
            {openSections["risk_matrix"] && (
              <>
                <Separator />
                <CardContent className="pt-4 pb-2 overflow-x-auto">
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="bg-muted/50">
                        {["Entity", ...dimensionNames, "Overall", "Priority Action"].map(h => (
                          <th key={h} className="px-3 py-2 text-left text-xs font-bold uppercase tracking-wider text-muted-foreground border-b border-border">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row, i) => (
                        <tr key={i} className="border-b border-border/50 hover:bg-muted/20">
                          <td className="px-3 py-2 font-semibold text-foreground">{row.entity}</td>
                          {dimensionNames.map(dim => (
                            <td key={dim} className="px-3 py-2"><RiskBadge level={row.dimensions[dim]} /></td>
                          ))}
                          <td className="px-3 py-2"><RiskBadge level={row.overall} /></td>
                          <td className="px-3 py-2 text-xs text-muted-foreground">{row.priority_action}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardContent>
              </>
            )}
          </Card>
        )
      })()}

      {/* ── Conclusions ── */}
      {report.conclusions && (
        <Card className="border-foreground/10">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-foreground flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-success" />
              Conclusions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <CitedText text={report.conclusions} className="text-sm text-foreground/80 leading-relaxed" />
          </CardContent>
        </Card>
      )}

      {/* ── Recommendations ── */}
      {report.recommendations?.length > 0 && (
        <Card className="border-success/20 bg-success/5">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-success">Recommendations</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="list-decimal pl-5 space-y-2">
              {report.recommendations.map((rec, i) => (
                <li key={i} className="text-sm text-foreground/80 leading-relaxed">{rec}</li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}

      {/* ── Sub-analysis data / citation sources ── */}
      {citableSources.length > 0 && (
        <Card>
          <button
            onClick={() => toggleSection("sub_data")}
            className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-muted/30 transition-colors cursor-pointer rounded-lg text-left"
          >
            <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <Database className="w-4 h-4 text-muted-foreground" />
              Sources
            </span>
            <Badge variant="secondary" className="text-label">{citableSources.length} analyses</Badge>
          </button>
          {openSections["sub_data"] && (
            <>
              <Separator />
              <CardContent className="pt-4 pb-2">
                <div className="flex flex-col gap-6">
                  {citableSources.map((source, i) => {
                    const r = task?.sub_results?.[source.question] || {}
                    return (
                      <div key={source.id} id={`source-${source.id}`} className="scroll-mt-20">
                        <div className="flex items-start gap-2 mb-3">
                          <div className="w-5 h-5 rounded-full bg-foreground flex items-center justify-center shrink-0 mt-0.5">
                            <span className="text-label font-bold text-background">{source.id}</span>
                          </div>
                          <p className="text-sm font-semibold text-foreground">{source.question}</p>
                        </div>
                        {r.summary && <p className="text-xs text-muted-foreground mb-3 pl-7">{r.summary}</p>}
                        {r.columns && r.rows?.length > 0 && (
                          <div className="pl-7"><MiniChart rows={r.rows} columns={r.columns} /></div>
                        )}
                        {i < citableSources.length - 1 && <Separator className="mt-4" />}
                      </div>
                    )
                  })}
                </div>
              </CardContent>
            </>
          )}
        </Card>
      )}

      {/* ── Dataset footer ── */}
      {report.data_coverage?.datasets_used?.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap px-1">
          <span className="text-label text-muted-foreground font-medium uppercase tracking-wider">Datasets:</span>
          {report.data_coverage.datasets_used.map(d => (
            <Badge key={d} variant="secondary" className="text-label font-mono">{d}</Badge>
          ))}
        </div>
      )}

      {/* ── Follow-up bar ── */}
      <div className="sticky bottom-0 -mx-6 px-6 pb-4 pt-4 bg-gradient-to-t from-background via-background/95 to-transparent z-30 print:hidden">
        <form onSubmit={handleSubmit}>
          <Card className="shadow-md border-border focus-within:ring-2 focus-within:ring-ring/20 focus-within:border-foreground/30 transition-all">
            <CardContent className="p-2 flex items-center gap-2">
              <div className="flex items-center gap-1 shrink-0">
                <button type="button" onClick={() => setFollowUpMode("qa")}
                  className={`text-label px-2 py-1 rounded font-medium transition-colors ${followUpMode === "qa" ? "bg-foreground text-background" : "text-muted-foreground hover:text-foreground"}`}>
                  QA
                </button>
                <button type="button" onClick={() => setFollowUpMode("report")}
                  className={`text-label px-2 py-1 rounded font-medium transition-colors ${followUpMode === "report" ? "bg-foreground text-background" : "text-muted-foreground hover:text-foreground"}`}>
                  Report
                </button>
              </div>
              <Separator orientation="vertical" className="h-5" />
              <Input value={followUpText} onChange={e => setFollowUpText(e.target.value)}
                placeholder="Ask a follow-up or request a new report section..."
                className="border-none bg-transparent shadow-none focus-visible:ring-0 h-9 text-sm" />
              <Button type="submit" disabled={!followUpText.trim()} size="sm" className="gap-1.5 shrink-0">
                <Send className="w-3 h-3" />Run
              </Button>
            </CardContent>
          </Card>
        </form>
      </div>
    </div>
  )
}
