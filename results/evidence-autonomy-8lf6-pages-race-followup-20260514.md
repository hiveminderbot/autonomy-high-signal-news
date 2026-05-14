# Follow-up evidence for autonomy-8lf6 — GitHub Pages deploy race fixed

Date: 2026-05-14T04:18Z

After the first close-out, a post-push live check briefly showed the GitHub Pages root serving a stale `2026-05-09` dashboard. Root cause: `.github/workflows/deploy-dashboard.yml` also triggered on `push` and raced the canonical `.github/workflows/pages.yml`, overwriting the current briefing with `dashboard/index.html`.

## Fix
- Changed `.github/workflows/deploy-dashboard.yml` to `workflow_dispatch` only.
- Added regression coverage in `tests/test_pages_workflow_selection.py` asserting the legacy workflow no longer deploys on push and documenting `pages.yml` as the canonical Pages deploy path.

## Validation

```text
./scripts/run-with-nix-python.sh -m pytest tests/test_pages_workflow_selection.py -q
2 passed in 0.03s

./scripts/run-with-nix-python.sh -m pytest -q
319 passed, 6 warnings in 36.23s

git diff --check
PASS
```

## Commit / push

```text
e833af3 fix: prevent legacy dashboard pages deploy race
39667ea docs: add validation evidence for autonomy-8lf6
fb605e0 chore: refresh May 14 briefing timestamp
```

Pushed to GitHub remote `github/main`.

## Live public dashboard re-check

```text
URL: https://hiveminderbot.github.io/autonomy-high-signal-news/
POLL 0 bytes 15735 date True stories 20 title ['Morning Briefing - Thursday, May 14, 2026'] ok True
```

The public root URL is now serving the current-date May 14 briefing with 20 story cards.
