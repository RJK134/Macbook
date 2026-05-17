# Bugbot rules for this repository

These are repository-specific patterns Bugbot must surface as **Medium severity** or higher whenever a PR touches `.github/workflows/` or scaffolding files. They reflect bugs we have hit in this org and want auto-flagged on every future PR.

## 1. Duplicate Claude workflows on `issue_comment`

**Pattern**

The repository contains both `.github/workflows/claude.yml` and `.github/workflows/claude-code-fix.yml` (or any two workflow files) where each:

- Subscribes to `on: issue_comment` with `types: [created]`, AND
- Has a job-level `if:` that gates on `contains(github.event.comment.body, '@claude')`.

**Why it matters**

A single `@claude` mention in any issue or PR comment fires both workflows in parallel. Each runs `anthropics/claude-code-action` with a different prompt — one as a "bug-fixing agent", one as a "general assistant" — producing:

- Doubled `ANTHROPIC_API_KEY` spend on every mention.
- Racing PRs that overwrite each other.
- Confusing duplicate notifications on the source issue / PR.

**Required fix**

Keep exactly one workflow file (the pinned one, typically `claude.yml` at `anthropics/claude-code-action@<commit-sha>`). Delete the older unpinned one. If the deleted file had prompt-customisation logic worth preserving, fold it into the surviving workflow's `prompt:` block. Severity: **Medium**.

## 2. Missing `ANTHROPIC_API_KEY` repository secret

**Pattern**

A PR adds or modifies `.github/workflows/claude.yml` (or any workflow that calls `anthropics/claude-code-action`) and the repository does not have an `ANTHROPIC_API_KEY` secret configured at `Settings → Secrets and variables → Actions`.

**Why it matters**

The workflow's job-level `if:` will skip silently while no one `@claude`-mentions, so CI looks green at merge time. The first `@claude` mention after merge fails with an opaque `Bad credentials` error from the Anthropic API, blocking whatever bug or rebase the mention was trying to trigger — usually at exactly the moment the user is relying on it.

**Required fix**

Surface this in the PR review with a one-line nav path: `https://github.com/<owner>/<repo>/settings/secrets/actions`. Do **not** attempt to set the secret; only flag. Severity: **Medium**.

## 3. `merge_group` trigger without job-level `if:`

**Pattern**

A workflow declares `on: merge_group` but its jobs are gated `if: github.event_name == 'pull_request'` (or similar, without `|| github.event_name == 'merge_group'`).

**Why it matters**

Jobs always skip on merge-queue entries, so the merge queue passes with no real checks. The next breaking change lands silently.

**Required fix**

Every job under a workflow with `on: merge_group` must have an `if:` that includes `github.event_name == 'merge_group'` (alongside `pull_request` / `push` as needed). Severity: **Medium**.

## Cross-references

These rules were derived from:

- RJK134/Maieus2 #112 (duplicate `claude.yml` + `claude-code-fix.yml`, Bugbot finding, Medium).
- RJK134/herm-platform #151 (same pattern; rename-based fix).
- RJK134/Macbook #11 (`merge_group` without job-level `if:`).
