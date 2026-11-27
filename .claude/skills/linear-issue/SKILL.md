---
name: linear-issue
description: Repo conventions for Linear issues: target project, template, labels. Use whenever the user asks to create, file, open, log or write up an issue, ticket, task or bug, or to turn something from the conversation into one.
---

# Linear issue

Every issue goes to the Linear project **Ambient Data Brewing Monitor**
(https://linear.app/tcv-coding-space/project/ambient-data-brewing-monitor-2806fdd23b39), team `Solo` (key `SOL`). Look up the label IDs through the Linear MCP; don't guess them.

How to investigate, challenge and split a request lives in the personal `writing-tickets` skill. Without it: search the project for a duplicate, fill the template below, create the issue, reply with ID and link.

## Template

**Title:** imperative, ≤70 chars, no type prefix. `Add humidity bounds to reading ingest`, not `[Feature] Humidity`.

**Description:**
```md
## Why
1–3 lines: the problem or the value. For a bug: steps → expected → actual.

## Done when
- [ ] Observable outcome, checkable from outside (API response, rendered page, device behaviour)

## Notes
Pointers only: where to start (files, endpoints, docs), constraints, assumptions, what's out of scope.
```
- `## Why` and `## Done when` are required. Omit `## Notes` when empty.
- "Done when" items are the tests and the definition of done: each one checkable through a boundary (see "Tests" in `CLAUDE.md`), not an implementation step.
- A ticket that adds a route, accepts device input or changes insight logic lists the matching "Must test" cases from `CLAUDE.md` (auth, input bounds, status codes, edge cases) in "Done when".
- A ticket that adds or changes a page has a "Done when" item naming its click path from the header (`Dashboard → device name → Start batch`). No path yet: the ticket adds the link.
- Doc that must change with it (`firmware/README.md`, `ARCHITECTURE.md`): name it in Notes, not as a "Done when" item.
- Blocked-by goes in Linear's native relations, never in the description.
- Link, don't copy: name the file, endpoint or doc instead of pasting it.

## Fields
- **Type label** (exactly one), with the Conventional Commit it maps to: `Bug` → `fix:`, `Feature` → `feat:`, `Improvement` (refactor, deps, CI, tooling, docs, perf) → `refactor:` / `chore:` / `perf:` / `docs:`.
- **Area label** (at most one): `backend`, `frontend`, `devops` (infra, CI, deploys), `data_ops` (insights, analysis), `Misc` (docs, settings). Cross-cutting work takes the area where the change starts (a schema change is `backend`). Firmware has no label yet: omit.
- **Milestone** (exactly one): the work package the issue belongs to. List them with `list_milestones` on the project; they are numbered in the order to work on them. If none fits, ask before creating a new milestone.
- **Priority, estimate, assignee:** only if the user gives one.

## Never
- Put secrets, tokens or `.env` values in an issue, even redacted ones.
- Add sections, labels or fields beyond the above.
