# Cal.com signup browser-agent QA demo packet — 2026-05-05

Recommendation: **ADOPT_OUTREACH_PACKET_AFTER_REAL_BROWSER_TRACE**

## Bottom line
Cal.com remains a credible first outreach target for a browser-agent QA service, but the honest next conversion step is a real browser trace before any prospect email is sent.

## Source evidence
- URL: https://cal.com/signup
- HTTP: 200 final_url: https://app.cal.com/signup bytes: 401659 ok: True
- Title: Sign up | Cal.com
- Static visible text chars: 17 sample: Sign up | Cal.com
- Forms/inputs/buttons/scripts/noscript: 0/0/0/52/0
- Error: (none)

## Findings for a prospect-facing QA packet
1. **The public signup HTML exposes almost no visible signup content before JavaScript hydration.**
   - Severity/category: medium / resilience/first-paint
   - Why it matters: A blank/minimal first response gives a browser-agent QA demo a concrete conversion-risk hypothesis: JS, CDN, CSP, or client runtime failures can strand new users before account creation options are visible.
   - Repro: Fetch https://cal.com/signup; observe title-only visible text and no static form controls in the HTTP response.
2. **The signup page is heavily JavaScript-driven and has no <noscript> fallback in the fetched HTML.**
   - Severity/category: low / progressive-enhancement
   - Why it matters: This is not automatically a bug, but it is outreach-worthy because browser automation can cheaply verify whether the hydrated page degrades safely under common script/network failure modes.
   - Repro: Fetch https://cal.com/signup; count script tags and noscript tags in the response.
3. **No form/input/button controls are present in the public static response.**
   - Severity/category: medium / signup-discoverability
   - Why it matters: A paid QA monitor could repeatedly confirm whether account entry controls appear after hydration and capture regressions with screenshots/console/network logs.
   - Repro: Fetch https://cal.com/signup; static control counts are form=0/input=0/button=0.

## Outreach packet draft (do not send until browser trace passes)
- Subject: Public signup-flow QA finding for Cal.com
- Opening: I ran a source-backed public-entry QA pass on Cal.com's signup URL and found a concrete browser-automation demo target: the initial HTML response exposes almost no signup affordances before hydration.
- Offer: I can run a fixed-price browser-agent QA pass that captures screenshots, console/network evidence, and reproducible steps for signup-flow resilience without creating accounts or touching private user data.
- Guardrail: Do not send this as a claim of a confirmed production bug until a real browser trace reproduces the hydrated/loading behavior; this packet is a compliant pre-outreach demo scaffold.

## Next experiment
- Name: One-prospect real-browser trace
- Command shape: Run Playwright/browser-agent against https://cal.com/signup and capture screenshot + console + network failure evidence without account submission.
- Success gate: Send outreach only if a real browser trace confirms a reproducible loading, console, network, accessibility, or copy issue useful to Cal.com.

## Not revenue-ready because
- no prospect contacted and no paid reply/revenue evidence exists
- this run used public HTTP/static evidence; a real browser screenshot/console trace is still required before outreach
- browser-agent cost per useful report remains unmeasured

## Acceptance evidence
- Source healthy: True
- Finding count: 3
- Passed: True
