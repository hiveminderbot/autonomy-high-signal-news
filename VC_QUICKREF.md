# VC Quick Reference: High-Signal News Lab

> Quick reference for version control operations in the high-signal-news lab.
> **Full standards:** [../infrastructure/docs/vc-hygiene-standards.md](../infrastructure/docs/vc-hygiene-standards.md)

---

## Repository

| Property | Value |
|----------|-------|
| **Root** | `/home/exedev/autonomy/labs/high-signal-news/` |
| **Remote** | `http://localhost:3000/ferric/autonomy-high-signal-news` |
| **Main Branch** | `main` |
| **Pages Branch** | `pages` (auto-generated) |

---

## Quick Start

```bash
# One-time setup
cd /home/exedev/autonomy/labs/high-signal-news
git config commit.template .gitmessage

# Daily workflow
git checkout main && git pull --rebase
bd ready  # Find work
bd update <task-id> --claim

# ... do work ...

# Landing (MANDATORY)
git add -A
git commit -m "type(scope): description"
git push
bd update <task-id> --status closed
```

---

## Commit Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

|`feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`, `ci`, `build`, `revert`

### Scopes

- `newsletter` - Newsletter generation pipeline
- `sources` - RSS feed sources and discovery
- `curator` - Source curation and evaluation
- `scoring` - Content scoring algorithms
- `docs` - Documentation

### Examples

```bash
feat(newsletter): add parallel source fetching
fix(scoring): correct relevance weighting
docs(vc): add commit message template
test(sources): add RSS feed validation tests
```

---

## Branch Naming

Format: `type/description-bead-id`

```
feat/add-new-curator-autonomy-rx4
fix/scoring-bug-autonomy-7e4f
docs/vc-quickref-autonomy-qcml
```

---

## Pre-commit Hooks

```bash
# Run all hooks
pre-commit run --all-files

# Skip hooks (emergency only)
git commit --no-verify -m "fix: emergency patch"
```

---

## Common Commands

### Newsletter Generation

```bash
# Run newsletter pipeline
scripts/run-with-nix-python.sh scripts/generate_newsletter.py

# Test suite (preferred Nix validation gate)
./scripts/run-tests-nix.sh -v

# Validate sources
scripts/run-with-nix-python.sh scripts/validate_sources.py
```

### Git Operations

```bash
# Sync with remote
git checkout main
git pull --rebase

# Feature branch workflow
git checkout -b feat/my-feature-autonomy-XXXX
git add -A
git commit -m "feat(newsletter): add new feature"
git push -u origin feat/my-feature-autonomy-XXXX

# Clean up after merge
git checkout main
git pull --rebase
git branch -d feat/my-feature-autonomy-XXXX
```

---

## Lab-Specific Conventions

### Critical Files

| File | Purpose | Validation |
|------|---------|------------|
| `validation.json` | Validation configuration | Required |
| `STATUS.json` | Lab status tracking | Required |
| `src/curator/` | Source curation module | Tests must pass |
| `scripts/generate_newsletter.py` | Newsletter pipeline | Must run without errors |

### Protected Paths

- `src/curator/` - Core curation logic
- `sources/` - RSS source configurations
- `.forgejo/workflows/` - CI/CD configuration

---

## Workflows

### Adding News Source

```bash
# 1. Create branch
git checkout -b feat/add-source-autonomy-XXXX

# 2. Add source to sources/ directory

# 3. Validate source
scripts/run-with-nix-python.sh scripts/validate_sources.py

# 4. Commit and push
git add -A
git commit -m "feat(sources): add <source-name>

- Adds RSS feed for <description>
- Validated feed format
- Categorized under <category>

Refs: autonomy-XXXX"
git push

# 5. Complete
bd update autonomy-XXXX --status closed
```

---

## Emergency Procedures

### Push Rejected (Non-Fast-Forward)

```bash
git pull --rebase
# Resolve conflicts if any
git push
```

### Lost Work (Not Pushed)

```bash
# Find lost commits
git reflog

# Recover
git checkout -b recovery-branch <commit-hash>
```

---

## Contacts & Escalation

| Issue | Contact |
|-------|---------|
| Git/Forgejo issues | Check [../infrastructure/docs/ci-cd-integration.md](../infrastructure/docs/ci-cd-integration.md) |
| General questions | [../infrastructure/docs/vc-hygiene-standards.md](../infrastructure/docs/vc-hygiene-standards.md) |

---

**Last Updated:** 2026-03-23
**Document:** [../infrastructure/docs/vc-hygiene-standards.md](../infrastructure/docs/vc-hygiene-standards.md)
