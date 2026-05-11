# Browser-agent QA prospect shortlist — 2026-05-05

Recommendation: **ADOPT_BROWSER_AGENT_QA_PROSPECT_SPRINT**

## Bottom line
A browser-agent QA service sprint now has enough live public onboarding surfaces to run a concrete demo/outreach experiment rather than more abstract tooling research.

This is a prospect/demo shortlist, not proof of revenue and not a capital-ready claim.

## Top shortlist
- **Browserbase sign-up** (browser_agent_infra) — https://www.browserbase.com/sign-up
  - Title: Browserbase - Headless Web Browser API
  - HTTP: 200 bytes_minimum_met: True keyword_hits: browserbase, sign, browser
  - Why fit: A browser-automation infrastructure vendor is a meta-fit: their own onboarding can be evaluated with the service category they sell.
  - Demo hypothesis: Create a concise dogfood-style onboarding QA artifact focused on signup clarity and developer activation path.
- **Cal.com signup** (scheduling_saas) — https://cal.com/signup
  - Title: Sign up | Cal.com
  - HTTP: 200 bytes_minimum_met: True keyword_hits: cal, sign
  - Why fit: Scheduling onboarding usually has account creation, calendar/account connection, timezone, and team-routing complexity that browser agents can check repeatedly.
  - Demo hypothesis: Produce a signup/onboarding friction report covering field validation, auth options, and calendar-connection dead ends without touching private data.
- **Linear signup** (collaboration_saas) — https://linear.app/signup
  - Title: Linear
  - HTTP: 200 bytes_minimum_met: True keyword_hits: linear, signup
  - Why fit: Team/workspace creation has several branching onboarding states that can regress visibly and matter to conversion.
  - Demo hypothesis: Validate account/workspace-entry affordances and report any stalled or unclear browser states from a fresh public session.
- **PostHog signup** (product_analytics) — https://app.posthog.com/signup
  - Title: PostHog
  - HTTP: 200 bytes_minimum_met: True keyword_hits: posthog, signup
  - Why fit: Analytics onboarding depends on multi-step project creation and instrumentation guidance, a good fit for workflow-health and copy/friction checks.
  - Demo hypothesis: Check whether a new user can reach the first-project setup path and capture any confusing or blocked instrumentation steps.
- **Sentry signup** (developer_tools) — https://sentry.io/signup/
  - Title: Sign up for Sentry to start your free trial. | Sentry
  - HTTP: 200 bytes_minimum_met: True keyword_hits: sentry, sign, error
  - Why fit: Developer-tool onboarding combines auth, organization/project setup, and SDK-install instructions where broken or confusing flows are high-value.
  - Demo hypothesis: Generate a browser-agent transcript from landing on signup through first SDK/project prompts, highlighting friction and console/network errors.

## Next experiment
**One-day public onboarding QA demo sprint**

- One reproducible public-flow QA report per selected target, with screenshots/log snippets and no private-account actions beyond public signup entry points.
- One fixed-price service offer paragraph tied to the strongest report.
- A reject memo if no externally useful finding emerges within one day.

Success gate: Run browser-agent/Playwright diagnostics against the top 3 reachable targets and adopt the service wedge only if at least one artifact contains a reproducible public UX, console, network, or copy issue useful enough for credible outreach.

## Not revenue-ready because
- no live browser-agent runs against these targets were executed in this task
- no prospect contacted and no reply/revenue evidence exists yet
- no measured agent cost per useful report yet
- must respect public-site terms, rate limits, and avoid private data entry before outreach use

## All source evidence
- **Cal.com signup** — OK
  - URL: https://cal.com/signup
  - HTTP: 200 bytes_minimum_met: True
  - Keyword hits: cal, sign
  - Error: (none)
- **PostHog signup** — OK
  - URL: https://app.posthog.com/signup
  - HTTP: 200 bytes_minimum_met: True
  - Keyword hits: posthog, signup
  - Error: (none)
- **Sentry signup** — OK
  - URL: https://sentry.io/signup/
  - HTTP: 200 bytes_minimum_met: True
  - Keyword hits: sentry, sign, error
  - Error: (none)
- **Linear signup** — OK
  - URL: https://linear.app/signup
  - HTTP: 200 bytes_minimum_met: True
  - Keyword hits: linear, signup
  - Error: (none)
- **Supabase dashboard sign-up** — OK
  - URL: https://supabase.com/dashboard/sign-up
  - HTTP: 200 bytes_minimum_met: True
  - Keyword hits: supabase, sign, dashboard
  - Error: (none)
- **Browserbase sign-up** — OK
  - URL: https://www.browserbase.com/sign-up
  - HTTP: 200 bytes_minimum_met: True
  - Keyword hits: browserbase, sign, browser
  - Error: (none)
- **Vercel signup** — OK
  - URL: https://vercel.com/signup
  - HTTP: 200 bytes_minimum_met: True
  - Keyword hits: vercel, sign, deploy
  - Error: (none)

## Validation criteria
- Healthy targets: 7 / 5
- Segments present: browser_agent_infra, collaboration_saas, developer_platform, developer_tools, product_analytics, scheduling_saas
- Passed: True
