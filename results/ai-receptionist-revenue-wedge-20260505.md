# AI receptionist revenue wedge validation — 2026-05-05

Recommendation: **ADOPT_NARROW_AI_RECEPTIONIST_PILOT**

## Bottom line
A narrow AI receptionist service pilot is worth one lean validation sprint, not capital deployment.

This is a conversion candidate, not a proven business. It should advance only to a tiny demo + prospect test; it is not capital-ready.

## Why this is worth one lean pilot
- Realtime voice APIs plus commodity telephony make a concierge-style service technically feasible; competitor pricing pages show businesses already buy receptionist/call-handling outcomes.
- Guardrail: This is outside OpenViking/Polymarket and should be killed if a prospect shortlist and live demo cannot produce replies/meetings quickly.

## Next experiment
**10-prospect after-hours missed-call concierge pilot** (3 days)

- one Twilio/OpenAI demo phone number that answers, captures caller intent, and emails a lead summary
- a shortlist of 10 local appointment-based businesses with visible after-hours call friction
- outreach packet offering a fixed-price setup plus monthly managed answering pilot

Success gate: At least 2 human replies or 1 scheduled demo from 10 targeted prospects; otherwise reject or change vertical.

## Not capital-ready because
- no paying customer yet
- no measured cost-per-call, containment rate, or booking/revenue lift yet
- no production compliance/consent workflow for call recording and PII yet

## Source evidence
- **Twilio Programmable Voice pricing** — OK
  - URL: https://www.twilio.com/en-us/voice/pricing/us
  - Role: delivery_cost
  - HTTP: 200 bytes_minimum_met: True
  - Keyword hits: voice, pricing, Programmable Voice
  - Why cited: Primary vendor page for PSTN voice-call cost assumptions.
- **OpenAI Realtime API announcement** — OK
  - URL: https://developers.openai.com/blog/realtime-api
  - Role: technical_feasibility
  - HTTP: 200 bytes_minimum_met: True
  - Keyword hits: Realtime API, speech, audio
  - Why cited: Primary OpenAI developer source that realtime speech-to-speech API support exists.
- **Smith.ai pricing** — OK
  - URL: https://www.smith.ai/pricing
  - Role: competitor_willingness_to_pay
  - HTTP: 200 bytes_minimum_met: True
  - Keyword hits: pricing, receptionist, calls
  - Why cited: Competitor pricing page for outsourced receptionist / answering-service willingness to pay.
- **Slang.ai homepage** — OK
  - URL: https://www.slang.ai/
  - Role: vertical_competition
  - HTTP: 200 bytes_minimum_met: True
  - Keyword hits: AI, phone, restaurant
  - Why cited: AI phone agent competitor focused on restaurants, evidence that verticalized phone automation is an active category.

## Validation criteria
- Healthy sources: 4 / 3
- Required roles present: competitor_willingness_to_pay, delivery_cost, technical_feasibility, vertical_competition
- Passed: True
