"""Launcher kept for compatibility with v1.x: `python SRTAI_Translator.py` opens the app.

The code now lives in the `srtai` package. You can also run `python -m srtai`.
"""
import sys

from srtai.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
