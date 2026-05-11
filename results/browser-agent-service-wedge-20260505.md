# Browser-agent QA/service revenue wedge validation — 2026-05-05

Recommendation: **ADOPT_BROWSER_AGENT_QA_SERVICE_PILOT**

## Bottom line
Browser-agent QA/ops automation is worth one short service experiment because model, browser-control, and diagnostic surfaces now exist as primary-source-supported building blocks.

This is a service-experiment candidate, not a proven business or capital-ready project.

## Why this is worth one lean pilot
- MCP-connected browser automation, DevTools diagnostics, managed browser-agent SDKs, and computer-use model docs collectively make it feasible to package a narrow bug-reproduction or workflow-monitoring service without building a full product first.
- Guardrail: This is outside OpenViking/Polymarket and should be killed if a 48-hour demo cannot produce at least one externally useful QA artifact for a real public site or prospect workflow.

## Next experiment
**48-hour browser-agent QA artifact sprint** (2 days)

- Pick 3 small SaaS/ecommerce websites with public signup/cart/demo flows and visible complexity.
- Use Playwright/DevTools/LLM browser agents to produce one reproducible bug report or workflow-health report per target.
- Package the best report as an outreach artifact offering a fixed-price weekly browser-agent QA monitor.

Success gate: Adopt only if at least one report contains a reproducible externally visible issue or concrete UX/conversion fix that could plausibly justify paid outreach; otherwise reject this wedge for now.

## Not capital-ready because
- no paying customer or prospect reply yet
- no measured cost per successful browser task or failure triage yet
- no proof that agent-generated QA reports beat a human checklist for this market
- no production monitoring, consent, or anti-abuse process for third-party websites yet

## Source evidence
- **Microsoft Playwright MCP repository** — OK
  - URL: https://github.com/microsoft/playwright-mcp
  - Role: automation_surface
  - HTTP: 200 bytes_minimum_met: True
  - Keyword hits: Playwright, MCP, browser
  - Why cited: Primary source showing Playwright has an MCP server for browser automation through agent tools.
- **Chrome DevTools MCP repository** — OK
  - URL: https://github.com/ChromeDevTools/chrome-devtools-mcp
  - Role: diagnostic_surface
  - HTTP: 200 bytes_minimum_met: True
  - Keyword hits: Chrome, DevTools, MCP
  - Why cited: Primary source for using Chrome DevTools as an MCP-connected browser diagnostics surface.
- **Browserbase Stagehand introduction** — OK
  - URL: https://docs.browserbase.com/stagehand/introduction
  - Role: agent_sdk
  - HTTP: 200 bytes_minimum_met: True
  - Keyword hits: Stagehand, Browserbase, browser
  - Why cited: Primary vendor documentation for an agent-friendly browser automation SDK/API surface.
- **Anthropic computer use documentation** — OK
  - URL: https://docs.anthropic.com/en/docs/agents-and-tools/computer-use
  - Role: model_capability
  - HTTP: 200 bytes_minimum_met: True
  - Keyword hits: computer use, tool, Claude
  - Why cited: Primary model-provider documentation that computer-use/browser-control capabilities are supported for agents.

## Validation criteria
- Healthy sources: 4 / 4
- Required roles present: agent_sdk, automation_surface, diagnostic_surface, model_capability
- Passed: True
