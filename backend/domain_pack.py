"""
Domain configuration for report generation.

The core DS-STAR pipeline (Analyzer/Planner/Coder/Debugger/Verifier/Router) is already
fully domain-agnostic — it reasons from whatever data and question it's given. This file
configures the two places that used to hardcode a specific domain (financial-crime
compliance): the Writer's report persona, and an optional topic hint for the sub-question
generator.

To point a deployment at a specific domain, edit the values below. See
domain_packs/fraud_aml_example.py for a preserved reference of the original CBUAE/AML
deployment this app was first built for — copy from it, or use it as a template.
"""

# The Writer's voice/persona when writing a synthesised report.
REPORT_PERSONA = "You are a senior data analyst writing a report for a business stakeholder."

# Optional confidentiality/classification label stamped on generated reports
# (e.g. "INTERNAL — CONFIDENTIAL"). Set to None to omit it entirely.
REPORT_CLASSIFICATION = None

# Optional list of analytical dimensions to nudge the sub-question generator toward,
# e.g. ["Revenue trends", "Customer segments", "Regional performance"]. Leave empty to
# let the LLM choose the most relevant angles for each query on its own — this is the
# paper-faithful default and works for any domain without configuration.
SUBQUESTION_DIMENSIONS = []
