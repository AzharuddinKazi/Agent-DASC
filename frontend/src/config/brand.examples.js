// Example brand config: the original financial-crime-compliance (FIP / CBUAE) branding
// this app first shipped with. Not imported anywhere — copy `fraudAmlExample` into
// brand.js's `brand` export to use it, or use it as a template for a different domain.
import {
  TrendingUp, Flag, BarChart3, ShieldCheck,
  BarChart2, AlertTriangle, FileText, BookOpen, Search,
} from "lucide-react"

export const fraudAmlExample = {
  appName: "FIP",
  appShortCode: "FIP",
  tagline: "Financial Intelligence Platform",

  capabilities: [
    { icon: TrendingUp,  label: "SAR Analysis"   },
    { icon: Flag,        label: "Risk Scoring"   },
    { icon: BarChart3,   label: "Entity Ranking" },
    { icon: ShieldCheck, label: "AML Detection"  },
  ],

  templates: [
    { icon: BarChart2,     color: "blue",   type: "qa",     text: "Which LFIs have the highest card fraud loss rate vs. the peer median this quarter?" },
    { icon: TrendingUp,    color: "blue",   type: "qa",     text: "Show me fraud typology trends by channel across UAE banks over the past 12 months." },
    { icon: AlertTriangle, color: "blue",   type: "qa",     text: "Which LFIs are statistical outliers in their social engineering fraud detection rate?" },
    { icon: FileText,      color: "purple", type: "report", text: "Generate a thematic analysis of APP fraud growth across UAE banks in 2024." },
    { icon: BookOpen,      color: "purple", type: "report", text: "Produce a sector-wide fraud trend report for H1 2025 suitable for a supervisory letter annex." },
    { icon: Search,        color: "amber",  type: "qa",     text: "Which LFIs have declining STR filing rates compared to the prior quarter?" },
  ],

  modeLabels: { qa: "FIP-Insight", report: "FIP-Research" },

  footerText: "FIP · Financial Intelligence Platform · CBUAE Internal · Air-gapped",

  user: { initials: "AK", name: "Azharuddin Kazi", role: "Fraud Prevention" },
}
