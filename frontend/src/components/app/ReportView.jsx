import { useState, useMemo } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { ChevronRight, ChevronDown, Send, FileText, Database, CheckCircle2 } from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell
} from "recharts"

const CHART_COLORS = ["#18181b", "#52525b", "#16a34a", "#d97706", "#dc2626", "#2563eb"]
const TICK_STYLE   = { fontSize: 11, fill: "#71717a", fontFamily: "var(--font-sans)" }
const TIP_STYLE    = { fontSize: 12, border: "1px solid #e4e4e7", borderRadius: 6, boxShadow: "0 2px 8px rgba(0,0,0,.06)" }

// Prose renderer for the markdown report body
function ReportProse({ text }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: ({ children }) => <h1 className="text-xl font-bold text-foreground mt-6 mb-3 first:mt-0">{children}</h1>,
        h2: ({ children }) => <h2 className="text-base font-bold text-foreground mt-5 mb-2">{children}</h2>,
        h3: ({ children }) => <h3 className="text-sm font-semibold text-foreground mt-4 mb-1.5">{children}</h3>,
        p:  ({ children }) => <p className="text-sm text-muted-foreground leading-relaxed mb-3">{children}</p>,
        ul: ({ children }) => <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal pl-5 mb-3 space-y-1">{children}</ol>,
        li: ({ children }) => <li className="text-sm text-muted-foreground leading-relaxed">{children}</li>,
        strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
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
        td: ({ children }) => <td className="px-3 py-2 text-sm text-muted-foreground border-b border-border/50">{children}</td>,
      }}
    >
      {text}
    </ReactMarkdown>
  )
}

// Mini bar chart for a sub-result
function MiniChart({ rows, columns }) {
  if (!rows || rows.length === 0 || !columns || columns.length < 2) return null
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
        <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" horizontal={false} />
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

export default function ReportView({ task, query, onFollowUp }) {
  const [openSections, setOpenSections] = useState({})
  const [followUpText, setFollowUpText] = useState("")
  const [followUpMode, setFollowUpMode] = useState("report")

  const toggleSection = key => setOpenSections(s => ({ ...s, [key]: !s[key] }))

  // Parse the draft_report JSON
  const report = useMemo(() => {
    const raw = task?.final_result
    if (!raw) return null
    try {
      let s = typeof raw === "string" ? raw.trim() : JSON.stringify(raw)
      if (s.startsWith("```")) s = s.replace(/^```[a-z]*\n?/, "").replace(/```$/, "").trim()
      return JSON.parse(s)
    } catch { return null }
  }, [task?.final_result])

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
    <div className="flex flex-col gap-5 pb-24 w-full">

      {/* ── Report header ── */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <FileText className="w-4 h-4 text-muted-foreground" />
            <Badge variant="secondary" className="text-[10px] font-bold uppercase tracking-wider">DS-STAR+ Research Report</Badge>
          </div>
          <h1 className="text-xl font-bold text-foreground leading-tight">{report.title || query}</h1>
        </div>
        {report.data_coverage && (
          <div className="flex items-center gap-4 shrink-0 text-right">
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
      </div>

      {/* ── Executive summary ── */}
      <Card className="border-foreground/10 bg-foreground text-background">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold text-background/90">Executive Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-background/80 leading-relaxed">{report.executive_summary}</p>
        </CardContent>
      </Card>

      {/* ── Report sections ── */}
      {(report.sections || []).map((section, i) => (
        <Card key={i}>
          <button
            onClick={() => toggleSection(i)}
            className="w-full flex items-center justify-between px-5 py-4 hover:bg-muted/30 transition-colors cursor-pointer rounded-t-lg"
          >
            <div className="flex items-center gap-3 text-left">
              <div className="w-6 h-6 rounded-full bg-foreground flex items-center justify-center shrink-0">
                <span className="text-[10px] font-bold text-background">{i + 1}</span>
              </div>
              <div>
                <p className="text-sm font-semibold text-foreground">{section.heading}</p>
                {section.key_stat && (
                  <p className="text-xs text-muted-foreground mt-0.5">{section.key_stat}</p>
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
                {section.sub_question && (
                  <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-3">
                    Sub-analysis: {section.sub_question}
                  </p>
                )}
                <ReportProse text={section.body} />
              </CardContent>
            </>
          )}
        </Card>
      ))}

      {/* ── Sub-analysis data cards (collapsible) ── */}
      {task?.sub_results && Object.keys(task.sub_results).length > 0 && (
        <Card>
          <button
            onClick={() => toggleSection("sub_data")}
            className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-muted/30 transition-colors cursor-pointer rounded-lg"
          >
            <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
              {openSections["sub_data"] ? <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" /> : <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />}
              <Database className="w-4 h-4 text-muted-foreground" />
              Sub-analysis Data
            </span>
            <Badge variant="secondary" className="text-[10px]">{Object.keys(task.sub_results).length} analyses</Badge>
          </button>
          {openSections["sub_data"] && (
            <>
              <Separator />
              <CardContent className="pt-4 pb-2">
                <div className="flex flex-col gap-6">
                  {Object.entries(task.sub_results).map(([q, r], i) => (
                    <div key={i}>
                      <div className="flex items-start gap-2 mb-3">
                        <CheckCircle2 className="w-4 h-4 text-success shrink-0 mt-0.5" />
                        <p className="text-sm font-semibold text-foreground">{q}</p>
                      </div>
                      {r.summary && <p className="text-xs text-muted-foreground mb-3 pl-6">{r.summary}</p>}
                      {r.columns && r.rows && r.rows.length > 0 && (
                        <div className="pl-6">
                          <MiniChart rows={r.rows} columns={r.columns} />
                        </div>
                      )}
                      {i < Object.keys(task.sub_results).length - 1 && <Separator className="mt-4" />}
                    </div>
                  ))}
                </div>
              </CardContent>
            </>
          )}
        </Card>
      )}

      {/* ── Conclusions ── */}
      {report.conclusions && (
        <Card className="border-success/20 bg-success/5">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-success flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4" />
              Conclusions & Recommendations
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-foreground leading-relaxed">{report.conclusions}</p>
          </CardContent>
        </Card>
      )}

      {/* ── Data coverage footer ── */}
      {report.data_coverage?.datasets_used?.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap px-1">
          <span className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">Datasets:</span>
          {report.data_coverage.datasets_used.map(d => (
            <Badge key={d} variant="secondary" className="text-[10px] font-mono">{d}</Badge>
          ))}
        </div>
      )}

      {/* ── Follow-up bar ── */}
      <div className="sticky bottom-0 -mx-6 px-6 pb-4 pt-4 bg-gradient-to-t from-background via-background/95 to-transparent z-30">
        <form onSubmit={handleSubmit}>
          <Card className="shadow-md border-border focus-within:ring-2 focus-within:ring-ring/20 focus-within:border-foreground/30 transition-all">
            <CardContent className="p-2 flex items-center gap-2">
              <div className="flex items-center gap-1 shrink-0">
                <button
                  type="button"
                  onClick={() => setFollowUpMode("qa")}
                  className={`text-[11px] px-2 py-1 rounded font-medium transition-colors ${followUpMode === "qa" ? "bg-foreground text-background" : "text-muted-foreground hover:text-foreground"}`}
                >QA</button>
                <button
                  type="button"
                  onClick={() => setFollowUpMode("report")}
                  className={`text-[11px] px-2 py-1 rounded font-medium transition-colors ${followUpMode === "report" ? "bg-foreground text-background" : "text-muted-foreground hover:text-foreground"}`}
                >Report</button>
              </div>
              <Separator orientation="vertical" className="h-5" />
              <Input
                value={followUpText}
                onChange={e => setFollowUpText(e.target.value)}
                placeholder="Follow up — e.g. 'Drill into exchange houses' or 'Add trend analysis'"
                className="border-none bg-transparent shadow-none focus-visible:ring-0 h-9 text-sm"
              />
              <Button type="submit" disabled={!followUpText.trim()} size="sm" className="gap-1.5 shrink-0">
                <Send className="w-3 h-3" />
                Run
              </Button>
            </CardContent>
          </Card>
        </form>
      </div>
    </div>
  )
}
