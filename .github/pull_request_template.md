<!--
Title: a Conventional Commit, imperative, ≤72 chars. On squash merge it becomes the commit on main.
  feat(frontend): adopt shadcn as the enforced design system
Link the issue below: "Fixes #123" closes it on merge, "Part of #123" only links it.
Delete these comments and any section marked optional when it's empty.
-->

Fixes #

## Why
<!-- 1–3 lines: the problem or the value. Link the issue; don't restate it. -->

## What changed
<!-- Bullets a reviewer can check against the diff. Name what you reused, or why nothing fit. -->

## Verified
<!-- What you checked beyond CI (CI runs `make check` and `make smoke`): an API call, the rendered page, a device run. Screenshot for UI changes. -->

## Review focus (optional)
<!-- The risky part, a trade-off, or an open question. -->

## Flags (optional)
<!-- Keep only the lines that apply. -->
- New dependency: `name` (why, what it replaces)
- Migration: read the generated file
- Device contract (`/api/v1`, `firmware/README.md`) touched, still non-breaking because …
- New env var, added to `.env.example`
- Follow-up: #
