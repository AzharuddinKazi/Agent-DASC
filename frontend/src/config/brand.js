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

  // Example queries shown on the New Analysis screen, filtered by the active mode tab.
  // type is "qa" (quick analysis / Insight) or "report" (multi-step research report).
  // Written against the shape of the sample UAE fraud/AML dataset
  // (backend/generate_synthetic_data.py) — swap these out for a different domain.
  templates: [
    { icon: BarChart2,     color: "blue",   type: "qa",     text: "Which LFIs have the highest share of suspicious transactions relative to their total volume?" },
    { icon: Flag,          color: "blue",   type: "qa",     text: "Show me structuring transactions clustered just under the AED 55,000 reporting threshold." },
    { icon: AlertTriangle, color: "blue",   type: "qa",     text: "Which customer segments (nationality, income band) are most associated with remittance structuring?" },
    { icon: Search,        color: "amber",  type: "qa",     text: "Which PEP-flagged customers have unusually large or irregular wire transfers?" },
    { icon: Table2,        color: "blue",   type: "qa",     text: "Compare STR filing rates across AML typologies — which categories are under-reported?" },
    { icon: ShieldCheck,   color: "amber",  type: "qa",     text: "Which exchange houses show the highest concentration of crypto off-ramp cash withdrawals?" },
    { icon: FileText,      color: "purple", type: "report", text: "Produce a supervisory report on trade-based money laundering exposure across free-zone corporate accounts." },
    { icon: BookOpen,      color: "purple", type: "report", text: "Generate a thematic analysis of fraud and AML typology trends across institutions and emirates in 2025." },
    { icon: TrendingUp,    color: "purple", type: "report", text: "Assess KYC and onboarding-channel risk gaps across the customer base and recommend remediation priorities." },
  ],

  // Labels for the two pipeline modes (quick analysis vs. multi-step report).
  modeLabels: { qa: "Insight", report: "Research" },

  footerText: "Powered by DS-STAR",
}
