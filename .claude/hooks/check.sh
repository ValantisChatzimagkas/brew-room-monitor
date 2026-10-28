#!/usr/bin/env bash
# Stop: before Claude ends a turn, run the fast static checks for whichever side it changed.
# Exit 2 sends the errors back to Claude. Tests and `next build` stay in `make check` / CI.
set -uo pipefail
cd "$CLAUDE_PROJECT_DIR"

# Skip when no uncommitted file changed since the last passing run (e.g. a Q&A turn).
stamp="$(git rev-parse --git-dir)/claude-stop-check"
changed=()
while IFS= read -r f; do
  [[ -f "$f" && ( ! -e "$stamp" || "$f" -nt "$stamp" ) ]] && changed+=("$f")
done < <(git ls-files --modified --others --exclude-standard)
(( ${#changed[@]} )) || exit 0

touched() { printf '%s\n' "${changed[@]}" | grep -q "^$1/"; }

failed=0
if touched backend; then
  (cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy .) >&2 || failed=1
fi
if touched frontend; then
  (cd frontend && pnpm --silent lint && pnpm --silent typecheck) >&2 || failed=1
fi

if (( failed )); then
  echo "Fix the errors above before finishing." >&2
  exit 2
fi
touch "$stamp"
