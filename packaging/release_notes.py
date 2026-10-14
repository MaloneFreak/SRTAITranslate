"""Write the release notes for a version (used by the release workflow).

    python packaging/release_notes.py v2.0.0 release_notes.md

Uses docs/release-notes/<version>.md when it exists, otherwise the version's
section of CHANGELOG.md.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def candidates(version: str) -> list[str]:
    parts = version.split(".")
    names = [version]
    while len(parts) < 3:
        parts.append("0")
        names.append(".".join(parts))
    return names


def notes_for(version: str) -> str:
    for name in candidates(version):
        path = ROOT / "docs" / "release-notes" / f"{name}.md"
        if path.is_file():
            return path.read_text(encoding="utf-8").strip() + "\n"
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    for section in re.split(r"(?m)^## ", text):
        if any(section.startswith(f"[{n}]") or section.startswith(n) for n in candidates(version)):
            body = section.split("\n", 1)[1].strip()
            return body + "\n\n---\nDownload `SRTAI_Translator.exe` below. No installation needed; models download on demand.\n"
    return f"SRT AI Translator {version}\n"


def main() -> int:
    version = sys.argv[1].lstrip("vV") if len(sys.argv) > 1 else ""
    notes = notes_for(version)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(notes, encoding="utf-8")
    else:
        sys.stdout.buffer.write(notes.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
