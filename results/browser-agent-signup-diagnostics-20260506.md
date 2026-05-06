# Browser-agent signup diagnostics — 2026-05-06

Recommendation: **ADOPT_PUBLIC_BROWSER_AGENT_QA_DEMO**

## Bottom line
The browser-agent QA wedge has a concrete public-flow demo path: at least one top prospect exposes a diagnosable signup/onboarding surface that can be converted into a safe outreach artifact.

## Fixed-price service offer draft
Offer: I run a fixed-price public onboarding QA pass against your signup flow using browser automation plus HTTP/console/network evidence, then deliver a concise report with reproducible states, screenshots/log excerpts, and prioritized fixes. No private user data or account abuse; the first pass focuses only on public entry points and conversion-blocking friction.

## Strongest outreach target
- **Cal.com signup** — https://cal.com/signup
  - Segment: scheduling_saas
  - Title: Sign up | Cal.com
  - Static visible text chars: 17
  - Forms/inputs/buttons/scripts: 0/0/0/52
  - Finding: Static HTML exposes almost no visible signup copy before JavaScript execution; this is a credible browser-agent QA demo target for blank/loading-state and no-JS fallback capture.
  - Finding: Heavy JavaScript surface (52 script tags) has no <noscript> fallback; browser diagnostics should capture first-paint/loading and console/network failures.
  - Finding: No static form/input controls are present in the fetched signup HTML; a public browser run can validate whether account entry is discoverable after hydration.
  - Finding: No obvious identity-provider/auth option text appears in the public static response; browser-agent run should document auth-option discoverability.

## Per-target diagnostics
- **Browserbase sign-up** — https://www.browserbase.com/sign-up
  - HTTP: 200 final_url: https://www.browserbase.com/sign-up bytes_minimum_met: True
  - Title: Browserbase - Headless Web Browser API
  - Static visible text chars: 308 sample: Browserbase - Headless Web Browser API Welcome to Browserbase E-mail address * Phone number * 🇺🇸 +1 Need multiple accounts? Password * Continue Already have an account? Log in By continuing, you agree to Browserbase's Terms of Service with Privacy Policy and to receive periodic emails with updates. Get help
  - Forms/inputs/buttons/scripts/noscript: 1/4/2/38/False
  - Expected hits: browserbase, email, password, continue
  - Identity/auth hits: continue
  - Outreach-worthy: True
  - Finding: Heavy JavaScript surface (38 script tags) has no <noscript> fallback; browser diagnostics should capture first-paint/loading and console/network failures.
  - Finding: Static signup controls are visible without account creation; this is a good baseline target for copy, validation, and accessibility diagnostics.
- **Cal.com signup** — https://cal.com/signup
  - HTTP: 200 final_url: https://app.cal.com/signup bytes_minimum_met: True
  - Title: Sign up | Cal.com
  - Static visible text chars: 17 sample: Sign up | Cal.com
  - Forms/inputs/buttons/scripts/noscript: 0/0/0/52/False
  - Expected hits: cal, sign, signup
  - Identity/auth hits: (none)
  - Outreach-worthy: True
  - Finding: Static HTML exposes almost no visible signup copy before JavaScript execution; this is a credible browser-agent QA demo target for blank/loading-state and no-JS fallback capture.
  - Finding: Heavy JavaScript surface (52 script tags) has no <noscript> fallback; browser diagnostics should capture first-paint/loading and console/network failures.
  - Finding: No static form/input controls are present in the fetched signup HTML; a public browser run can validate whether account entry is discoverable after hydration.
  - Finding: No obvious identity-provider/auth option text appears in the public static response; browser-agent run should document auth-option discoverability.
- **Linear signup** — https://linear.app/signup
  - HTTP: 200 final_url: https://linear.app/signup bytes_minimum_met: True
  - Title: Linear
  - Static visible text chars: 15 sample: Linear Loading…
  - Forms/inputs/buttons/scripts/noscript: 0/0/0/9/False
  - Expected hits: linear, signup, loading
  - Identity/auth hits: (none)
  - Outreach-worthy: True
  - Finding: Static HTML exposes almost no visible signup copy before JavaScript execution; this is a credible browser-agent QA demo target for blank/loading-state and no-JS fallback capture.
  - Finding: No static form/input controls are present in the fetched signup HTML; a public browser run can validate whether account entry is discoverable after hydration.
  - Finding: No obvious identity-provider/auth option text appears in the public static response; browser-agent run should document auth-option discoverability.

## Acceptance evidence
- Reachable targets: 3 / 3
- Outreach-worthy targets: 3 / 1
- Passed: True

## Not revenue-ready because
- no prospect has been contacted and no paid reply exists
- these diagnostics are public HTTP/static evidence, not a full Playwright screenshot/console trace yet
- browser-agent cost per useful report is still unmeasured

## Next experiment
- Name: One-prospect browser-agent QA demo packet
- Target: Cal.com signup
- Success gate: Run a real browser automation trace against the strongest public target, attach screenshots/console/network snippets, and send one compliant outreach email only if the report contains a reproducible conversion or reliability issue.
