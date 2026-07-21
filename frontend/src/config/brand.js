// White-label branding and content config. Everything a specific deployment would want
// to customize lives here — component code should never hardcode a product name, example
// query, or capability label directly. See brand.examples.js for a preserved reference of
// the original CBUAE/AML branding this app first shipped with.
import {
  BarChart2, TrendingUp, AlertTriangle, FileText, BookOpen, Search,
  Flag, Table2, ShieldCheck,
} from "lucide-react"

export const brand = {
  appName: "Analytics Platform",
  appShortCode: "AP",
  tagline: "AI-powered data analysis",

  // Shown as pills under the brand mark on the New Analysis screen.
  capabilities: [
    { icon: TrendingUp,   label: "Trend Analysis"    },
    { icon: Flag,         label: "Anomaly Detection" },
    { icon: Table2,       label: "Entity Ranking"    },
    { icon: ShieldCheck,  label: "Data Quality"      },
  ],

  // Example queries shown on the New Analysis screen. type is "qa" (quick analysis) or
  // "report" (multi-step research report).
  templates: [
    { icon: BarChart2,     color: "blue",   type: "qa",     text: "Which entities have the highest value in [metric] this quarter?" },
    { icon: TrendingUp,    color: "blue",   type: "qa",     text: "Show me trends by category over the past 12 months." },
    { icon: AlertTriangle, color: "blue",   type: "qa",     text: "Which records are statistical outliers on [metric]?" },
    { icon: FileText,      color: "purple", type: "report", text: "Generate a thematic analysis of [topic] growth over the past year." },
    { icon: BookOpen,      color: "purple", type: "report", text: "Produce a sector-wide trend report suitable for a stakeholder briefing." },
    { icon: Search,        color: "amber",  type: "qa",     text: "Which entities have declining [metric] compared to the prior period?" },
  ],

  // Labels for the two pipeline modes (quick analysis vs. multi-step report).
  modeLabels: { qa: "Insight", report: "Research" },

  footerText: "Powered by DS-STAR",
}
