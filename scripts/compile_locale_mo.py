"""Compile .po files under locale/*/LC_MESSAGES/messages.po to .mo files.

This script will try to use polib if available. If not installed it will print
instructions for installing polib (pip install polib) or how to compile
manually with msgfmt tools.

Usage: python scripts/compile_locale_mo.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCALE_DIR = ROOT / "locale"


def compile_with_polib(po_path: Path, mo_path: Path) -> bool:
    try:
        import polib
    except Exception:
        return False

    pofile = polib.pofile(str(po_path))
    pofile.save_as_mofile(str(mo_path))
    return True


def main():
    if not LOCALE_DIR.exists():
        print("No locale directory found at", LOCALE_DIR)
        sys.exit(1)

    any_compiled = False
    for lang_dir in LOCALE_DIR.iterdir():
        lc_path = lang_dir / "LC_MESSAGES"
        po = lc_path / "messages.po"
        mo = lc_path / "messages.mo"
        if po.exists():
            print(f"Found: {po}")
            ok = compile_with_polib(po, mo)
            if ok:
                print(f"Compiled {po.name} -> {mo}")
                any_compiled = True
            else:
                print(f"polib not available. Skipping compilation for {po}.")
                print("Install polib (pip install polib) to compile .po to .mo automatically.")

    if not any_compiled:
        print("No .mo files compiled. If you installed polib, re-run this script.")


if __name__ == "__main__":
    main()
