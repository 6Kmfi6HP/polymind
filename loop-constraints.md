# Loop Constraints

## Paths
- Denylist: `.env*`, `**/secrets.*`, `**/pyproject.toml` unless the change is strictly adding a dependency, `**/migrations/*`

## Execution
- Auto-merge: NO. Default off.
- Attempt cap: 3 per item.
- L2 work MUST run in an isolated worktree.

## Human Gates
- Escalate before any `pyproject.toml` change.
- Escalate before any auth or security change.
- Escalate before any change touching more than 10 files.
- Escalate on the third failed attempt for the same item.
