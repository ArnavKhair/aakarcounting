# Agent rules for this repo

## Versioning and changelog: required on every push

The app has **no hard-coded version**. `/api/version` (`server.py`, `get_latest_version`) returns the
highest `vX.Y.Z` found in any markdown heading in `changelog/*.md`. Adding a `## vX.Y.Z` changelog
entry *is* the version bump. Never put a version number anywhere else.

### Log while you work

At the top of the current parent changelog (`changelog/CHANGELOG-v1.3.x.md`), directly under the
`## Version Goal` block and its `---`, keep a section headed exactly `## Unreleased`:

```markdown
## Unreleased

### What's added

- ...

### Fixed

- ...

### What's removed

- None

---
```

- When you commit a user-visible change or fix, add a bullet in the same commit.
- Write bullets in plain language, matching the existing entries: what changed and why it matters to the
  user, not a list of code edits.
- Put `None` under any sub-heading that has no entries.
- `Unreleased` has no semver, so it does not change the version the app shows.

### Before every push (to any branch, including `main`)

1. Rename `## Unreleased` to the next patch version: take the highest version across
   `changelog/*.md` and raise its last number by 1 (e.g. `v1.2.3` → `v1.2.4`).
2. Commit only that change with the message `Bump version to vX.Y.Z`.
3. Push. The `.githooks/pre-push` hook rejects a push if the version has not gone up, or if an
   `## Unreleased` heading is still there. Fix the changelog and push again.
   **Never** use `git push --no-verify`.

When a push adds a new version, GitHub Actions (`.github/workflows/changelog-release.yml`) automatically
creates a tag and a GitHub Release from that version's changelog section. Releases from branches other
than `main` are marked as pre-release. The bullets are therefore public release notes, so keep them clear
and user-facing. **Never create tags or releases by hand.**

If nothing user-visible changed since the last push, still add a version entry: a single bullet under
`### Fixed` or `### What's added` that describes the work.

### New parent version

If the work starts a new parent version (e.g. `v1.3`), **ask the user first**. Then create
`changelog/CHANGELOG-v1.3.x.md` with the same header as the current file: `# Parent Update: v1.3`,
a one-line summary, `**Branch:**`, and `## Version Goal`.

### Hook setup

If `git config core.hooksPath` does not print `.githooks`, run:

```sh
git config core.hooksPath .githooks
```

(`setup.bat` and `setup.sh` already do this.)
