"""Generate a messages.pot file containing all msgids found in templates.

This script collects all _('...') occurrences from Jinja templates and
writes a GNU gettext POT file `locale/messages.pot` which translators can
import into PO editors like Poedit.

Run: python scripts/generate_pot.py
"""
from __future__ import annotations

from pathlib import Path
import polib
import re

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT / 'app' / 'web' / 'templates'
OUT = ROOT / 'locale' / 'messages.pot'

MSG_RE = re.compile(r"_\(\s*['\"]([\s\S]*?)['\"]\s*\)")


def find_msgids() -> list[str]:
    msgids = []
    for p in sorted(TEMPLATES_DIR.rglob('*.html')):
        text = p.read_text(encoding='utf-8')
        for m in MSG_RE.finditer(text):
            mid = m.group(1)
            if mid not in msgids:
                msgids.append(mid)
    return msgids


def write_pot(msgids: list[str]):
    pot = polib.POFile()
    import datetime
    pot.metadata = {
        'POT-Creation-Date': datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M%z'),
        'Project-Id-Version': 'Luro 1.0',
        'MIME-Version': '1.0',
        'Content-Type': 'text/plain; charset=utf-8',
        'Content-Transfer-Encoding': '8bit',
    }
    for m in msgids:
        pot.append(polib.POEntry(msgid=m, msgstr=''))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pot.save(str(OUT))
    print('Wrote', OUT)


def main():
    msgids = find_msgids()
    print(f'Found {len(msgids)} msgids')
    write_pot(msgids)


if __name__ == '__main__':
    main()
