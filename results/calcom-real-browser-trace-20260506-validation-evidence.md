# Validation evidence — Cal.com real-browser signup QA trace — 2026-05-06

Bead: `autonomy-nb2`

Scope: non-OpenViking browser-agent QA revenue experiment. Passive public Cal.com signup trace only; no form submission, no account creation, no prospect contact.

## automated_tests

```text
$ scripts/run-with-nix-python.sh -m py_compile scripts/generate_calcom_real_browser_trace_20260506.py scripts/validate_calcom_real_browser_trace_20260506.py tests/test_calcom_real_browser_trace_20260506.py
high-signal-news dev shell ready
Python: Python 3.12.13

$ scripts/run-with-nix-python.sh -m pytest -q tests/test_calcom_real_browser_trace_20260506.py
high-signal-news dev shell ready
Python: Python 3.12.13
....                                                                     [100%]
4 passed in 0.03s

$ scripts/run-tests-nix.sh -q
high-signal-news dev shell ready
Python: Python 3.12.13
........................................................................ [ 27%]
........................................................................ [ 55%]
........................................................................ [ 83%]
..........................................                               [100%]
=============================== warnings summary ===============================
tests/test_newsletter_ingester.py::test_newsletter_entry_save_and_retrieve
tests/test_newsletter_ingester.py::test_newsletter_entry_save_and_retrieve
tests/test_newsletter_ingester.py::test_ingester_file_source
tests/test_newsletter_ingester.py::test_ingester_file_source
tests/test_newsletter_ingester.py::test_ingester_file_source
  /home/exedev/autonomy/labs/high-signal-news/scripts/aggregator/newsletter_ingester.py:150: DeprecationWarning: The default datetime adapter is deprecated as of Python 3.12; see the sqlite3 documentation for suggested replacement recipes
    conn.execute("""

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
258 passed, 5 warnings in 8.89s

$ git diff --check
# exit 0; no whitespace errors
```

## end_to_end_validation

```text
$ scripts/run-with-nix-python.sh scripts/generate_calcom_real_browser_trace_20260506.py
high-signal-news dev shell ready
Python: Python 3.12.13
CALCOM_REAL_BROWSER_TRACE_GENERATED REJECT_OUTREACH_UNTIL_STRONGER_TRACE screenshot_bytes 107172 body_text_chars 462

$ scripts/run-with-nix-python.sh scripts/validate_calcom_real_browser_trace_20260506.py
high-signal-news dev shell ready
Python: Python 3.12.13
end_to_end_validation
CALCOM_REAL_BROWSER_TRACE_E2E_OK
REPORT /home/exedev/autonomy/labs/high-signal-news/results/calcom-real-browser-trace-20260506.md BYTES 2578
JSON /home/exedev/autonomy/labs/high-signal-news/results/calcom-real-browser-trace-20260506.json BYTES 8400
SCREENSHOT /home/exedev/autonomy/labs/high-signal-news/results/calcom-real-browser-trace-20260506.png BYTES 107172
URL https://cal.com/signup STATUS 200 FINAL https://app.cal.com/signup
BODY_TEXT_CHARS 462
FINDINGS 4 RECOMMENDATION REJECT_OUTREACH_UNTIL_STRONGER_TRACE
```

## artifact_verification

- Report: `results/calcom-real-browser-trace-20260506.md` (2578 bytes)
- JSON: `results/calcom-real-browser-trace-20260506.json` (8400 bytes)
- Screenshot: `results/calcom-real-browser-trace-20260506.png` (107172 bytes)
- Recommendation: `REJECT_OUTREACH_UNTIL_STRONGER_TRACE`
- Reason for rejection: real browser trace loaded successfully and captured screenshot/console/network evidence, but it is not strong enough for automatic prospect outreach; no prospect contact or paid signal exists.

## decision

Validated rejection for outreach automation. This is a useful conversion step because it prevents sending a weak static-only/browser-only claim while preserving a reproducible trace artifact for manual review or a stronger future Playwright trace.
