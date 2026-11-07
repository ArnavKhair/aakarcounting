"""Find the latest changelog version and extract its release notes.

Usage: python changelog_release.py NOTES_PATH

Writes the notes for the highest vX.Y.Z changelog heading to NOTES_PATH and
emits ``version=vX.Y.Z`` to $GITHUB_OUTPUT (or stdout when run locally).
Standard library only, so CI doesn't need the app's dependencies.
"""

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHANGELOG_DIR = Path(os.environ.get("CHANGELOG_DIR", ROOT / "changelog"))

# Keep in sync with _SEMVER_HEADING in server.py, which decides the app's version.
SEMVER_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+.*?\bv?(\d+)\.(\d+)\.(\d+)\b")
# A section ends at the next heading of the same or higher level, or a rule.
SECTION_END = re.compile(r"^\s{0,3}(#{1,2}\s|---\s*$)")


def find_latest():
    """Return (version_tuple, lines, heading_index) for the highest version."""
    best = None
    for path in sorted(CHANGELOG_DIR.glob("*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            match = SEMVER_HEADING.match(line)
            if match:
                version = tuple(int(p) for p in match.groups())
                if best is None or version > best[0]:
                    best = (version, lines, i)
    return best


def section_notes(lines, start):
    body = []
    for line in lines[start + 1:]:
        if SECTION_END.match(line):
            break
        body.append(line)
    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()
    return "\n".join(body) + "\n"


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: changelog_release.py NOTES_PATH")
    latest = find_latest()
    if latest is None:
        sys.exit(f"No vX.Y.Z heading found in {CHANGELOG_DIR}/*.md")
    version_tuple, lines, start = latest
    version = "v" + ".".join(map(str, version_tuple))

    Path(sys.argv[1]).write_text(section_notes(lines, start), encoding="utf-8")

    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as fh:
            fh.write(f"version={version}\n")
    print(f"version={version}")


if __name__ == "__main__":
    main()
