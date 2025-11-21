"""Extract msgids from templates using _('...') and add them to .po files.

This is a small helper to collect strings already wrapped with _() and ensure
they exist in the PO files under locale/*/LC_MESSAGES/messages.po.

It requires polib (already installed in the venv) and will not overwrite
existing translations.
"""
from __future__ import annotations

import re
from pathlib import Path
import polib

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT / "app" / "web" / "templates"
LOCALE_DIR = ROOT / "locale"

MSG_RE = re.compile(r"_\(\s*['\"]([\s\S]*?)['\"]\s*\)")


def find_msgids() -> set[str]:
    msgids: set[str] = set()
    for p in TEMPLATES_DIR.rglob('*.html'):
        text = p.read_text(encoding='utf-8')
        for m in MSG_RE.finditer(text):
            msgids.add(m.group(1))
    return msgids


def ensure_in_po(lang_dir: Path, msgids: set[str]):
    po_path = lang_dir / 'LC_MESSAGES' / 'messages.po'
    if not po_path.exists():
        print(f"PO file not found: {po_path}")
        return
    po = polib.pofile(str(po_path))
    existing = {e.msgid for e in po}
    added = 0
    for m in sorted(msgids):
        if m not in existing:
            entry = polib.POEntry(msgid=m, msgstr='')
            po.append(entry)
            added += 1
    if added:
        po.save()
    print(f"Updated {po_path}: +{added} entries")


def main():
    msgids = find_msgids()
    print(f"Found {len(msgids)} msgids in templates.")
    for lang_dir in LOCALE_DIR.iterdir():
        if not lang_dir.is_dir():
            continue
        ensure_in_po(lang_dir, msgids)


if __name__ == '__main__':
    main()
