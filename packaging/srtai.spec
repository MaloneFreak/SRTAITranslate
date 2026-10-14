# PyInstaller spec for a single-file, windowed SRT AI Translator executable.
# Build with:  python packaging/build.py
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

ROOT = Path(SPECPATH).parent  # noqa: F821 (SPECPATH is provided by PyInstaller)
NAME = "SRTAI_Translator"

datas = [(str(ROOT / "srtai" / "assets"), "srtai/assets")]
datas += collect_data_files("customtkinter")
datas += collect_data_files("tkinterdnd2")
datas += collect_data_files("py3langid")
binaries = collect_dynamic_libs("ctranslate2")
hiddenimports = (
    collect_submodules("keyring.backends")
    + collect_submodules("srtai")
    + ["tkinterdnd2", "py3langid", "sentencepiece", "charset_normalizer"]
)
excludes = [
    "torch", "transformers", "tensorflow", "matplotlib", "scipy", "pandas", "IPython", "jupyter",
    "pytest", "PIL", "notebook", "sphinx", "huggingface_hub",
]

a = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

version_file = ROOT / "build" / "version_info.txt"
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=NAME,
    debug=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(ROOT / "srtai" / "assets" / ("icon.ico" if sys.platform == "win32" else "icon.png")),
    version=str(version_file) if version_file.exists() and sys.platform == "win32" else None,
)
