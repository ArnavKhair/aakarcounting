# Agent rules

**Read `CLAUDE.md` before making changes.** It is the single source of truth for agents in this repo.

In short:
- Log your work as you go under `## Unreleased` at the top of the current `changelog/CHANGELOG-vX.Y.x.md`.
- Before every push (to any branch or `main`), rename it to the next `## vX.Y.Z` and commit it as `Bump version to vX.Y.Z`. The app reads its version from that heading.
- The `.githooks/pre-push` hook enforces this. Never bypass it with `--no-verify`.
