"""Build the executable with PyInstaller.

    pip install -e .[dev]
    python packaging/build.py

The result is dist/SRTAI_Translator.exe (Windows) or dist/SRTAI_Translator (Linux/macOS).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from srtai import APP_NAME, __version__  # noqa: E402

VERSION_TEMPLATE = """VSVersionInfo(
  ffi=FixedFileInfo(filevers=({v0}, {v1}, {v2}, 0), prodvers=({v0}, {v1}, {v2}, 0), mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'MaloneFreak'),
      StringStruct('FileDescription', '{name}'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', 'SRTAI_Translator'),
      StringStruct('LegalCopyright', 'MIT License, Pedro Giacomo'),
      StringStruct('OriginalFilename', 'SRTAI_Translator.exe'),
      StringStruct('ProductName', '{name}'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def main() -> int:
    nums = [int(x) for x in __version__.split(".")[:3]] + [0, 0, 0]
    build_dir = ROOT / "build"
    build_dir.mkdir(exist_ok=True)
    (build_dir / "version_info.txt").write_text(
        VERSION_TEMPLATE.format(v0=nums[0], v1=nums[1], v2=nums[2], version=__version__, name=APP_NAME),
        encoding="utf-8",
    )
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
           "--distpath", str(ROOT / "dist"), "--workpath", str(build_dir / "pyinstaller"),
           str(ROOT / "packaging" / "srtai.spec")]
    print(" ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main())
