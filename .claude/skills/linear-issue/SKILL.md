---
name: linear-issue
description: Create or edit a Linear issue for this repo using the project template. Use whenever the user asks to create, file, open, log or write up an issue, ticket, task or bug, or to turn something from the conversation into one.
---

# Linear issue

Every issue goes to the Linear project **Ambient Data Brewing Monitor**
(https://linear.app/tcv-coding-space/project/ambient-data-brewing-monitor-2806fdd23b39). Look up its team and the label IDs through the Linear MCP; don't guess them.

## Steps
1. Search the project for an open issue covering the same thing. If one exists, update it or ask; don't create a duplicate.
2. Fill the template below. Create the issue directly; ask first only if the type, area or "Done when" is genuinely unclear.
3. Reply with the issue ID and link, nothing else.

## Template

**Title:** imperative, ≤70 chars, no type prefix. `Add humidity bounds to reading ingest`, not `[Feature] Humidity`.

**Description:**
```md
## Why
1–3 lines: the problem or the value. For a bug: steps → expected → actual.

## Done when
- [ ] Observable outcome, checkable from outside (API response, rendered page, device behaviour)

## Notes
Pointers only: file paths, links, constraints, what's out of scope.
```
- `## Why` and `## Done when` are required. Omit `## Notes` when empty.
- "Done when" items are the tests and the definition of done: each one checkable through a boundary (see "Tests" in `CLAUDE.md`), not an implementation step.
- Link, don't copy: name the file, endpoint or doc instead of pasting it.

## Fields
- **Labels:** exactly one per group.
  - Type: `Bug` (→ `fix:`), `Feature` (→ `feat:`), `Chore` (refactor, deps, CI, tooling, docs → `refactor:` / `chore:`).
  - Area: `Backend`, `Frontend`, `Firmware`, `Infra`. Cross-cutting work takes the area where the change starts (a schema change is `Backend`).
- **Priority, estimate, assignee:** only if the user gives one.

## Never
- Put secrets, tokens or `.env` values in an issue, even redacted ones.
- Add sections, labels or fields beyond the above.
