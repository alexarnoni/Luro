Luro — Translators guide
=========================

This project uses GNU gettext with Jinja2 templates. Translatable strings are
wrapped with the `_()` helper in templates, e.g. `{{ _('Create account') }}`.

Files and workflow
- `locale/messages.pot` — single extraction file (POT) generated from templates.
- `locale/<lang>/LC_MESSAGES/messages.po` — per-language PO files.
- `locale/<lang>/LC_MESSAGES/messages.mo` — compiled binary files used at runtime.

How to update POT
1. From project root run:

```powershell
& C:/projetos/Luro/.venv/Scripts/Activate.ps1
python scripts/generate_pot.py
```

2. This writes `locale/messages.pot`.

How to translate
1. Open `locale/messages.pot` in Poedit (or your preferred editor) and create a new translation for the target language.
2. Save the resulting `messages.po` under `locale/<lang>/LC_MESSAGES/messages.po`.
3. After editing PO files, compile them to MO so the app can load them:

```powershell
python scripts/compile_locale_mo.py
```

Notes
- We ship a small helper `scripts/auto_fill_pt.py` that can auto-fill obvious
  translations as a draft; please review and correct those entries.
- Keep msgids verbatim: changing the msgid in templates requires re-running the
  extraction and merging translations.

If you prefer, provide the PO file to a translator and they can edit with Poedit.
