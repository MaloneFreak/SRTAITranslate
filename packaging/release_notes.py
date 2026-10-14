"""Print the CHANGELOG section for a version (used by the release workflow)."""
import re
import sys
from pathlib import Path

version = sys.argv[1].lstrip("v") if len(sys.argv) > 1 else ""
text = Path(__file__).resolve().parent.parent.joinpath("CHANGELOG.md").read_text(encoding="utf-8")
sections = re.split(r"(?m)^## ", text)
for section in sections:
    if section.startswith(f"[{version}]") or section.startswith(version):
        body = section.split("\n", 1)[1].strip()
        print(body)
        print("\n---\nDownload `SRTAI_Translator.exe` below. No installation needed; models download on demand.")
        break
else:
    print(f"SRT AI Translator {version}")
