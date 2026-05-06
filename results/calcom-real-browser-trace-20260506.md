# Cal.com real-browser signup QA demo trace — 2026-05-06

Recommendation: **REJECT_OUTREACH_UNTIL_STRONGER_TRACE**

## Bottom line
A real headless Chromium trace now exists for the public Cal.com signup page. This upgrades the prior static-only scaffold into a browser-evidence demo packet, but it is still not revenue-ready because no prospect was contacted and no paid pilot exists.

## Browser trace evidence
- URL: https://cal.com/signup
- Final URL: https://app.cal.com/signup
- HTTP status: 200
- Title: Sign up | Cal.com
- Body text chars after hydration: 462
- Screenshot: results/calcom-real-browser-trace-20260506.png (107172 bytes)
- Forms/inputs/buttons/links/scripts: 0/1/4/1/76
- Auth/control terms observed: Continue with Google, Continue with Microsoft, Continue with Email, Sign in
- Console warning/error count: 7
- Failed request count: 5

## Findings
1. The public signup entry point loaded successfully in a real headless Chromium session.
2. The browser trace exposes account-entry/authentication affordances suitable for a compliant no-submit QA packet.
3. The trace captured failed network requests worth reviewing before any outreach claim is made.
4. Console warnings/errors were observed and can be included as diagnostic context if they reproduce.

## Outreach draft status
Do not send automatically. This trace is ready for internal manual review, not prospect delivery. If a later human-reviewed packet is sent, it should be framed as a small fixed-price public onboarding QA offer, not as a bug bounty or outage claim.

## Not revenue-ready / not capital-ready because
- no prospect contacted and no reply/revenue evidence exists
- no measured cost per useful browser-agent report yet
- this is one public passive trace, not a repeated monitoring deployment
- all private-account actions and form submissions were intentionally avoided

## Guardrails
- No form submission, account creation, login attempt, scraping behind auth, or prospect contact occurred.
- Any outreach must describe this as public passive QA evidence, not as proof of a production outage.
- OpenViking/Polymarket work is explicitly excluded from this artifact.

## Next experiment
- Send at most one compliant note only after human review confirms the screenshot and trace contain a useful, reproducible public onboarding observation.
- Reject this wedge for outreach if the screenshot/body text only shows a normal working signup page with no useful QA angle.

## Acceptance evidence
- Screenshot captured: True
- Finding count: 4
- Outreach-ready for manual review: False
