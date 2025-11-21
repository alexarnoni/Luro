"""Service helpers that power transaction import workflows."""
from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domain.accounts.models import Account
from app.domain.categories.models import Category
from app.domain.imports.schemas import ImportMode, ImportPreviewItem, ImportPreviewResponse, ImportSummary, ImportApplyResponse
from app.domain.rules.models import Rule
from app.domain.transactions.models import Transaction
from app.domain.users.models import User


CANONICAL_FIELDS = {"date", "description", "amount", "type", "account", "category"}
ALLOWED_EXTENSIONS = {".csv", ".ofx"}
MAX_FILE_BYTES = settings.IMPORT_MAX_FILE_MB * 1024 * 1024

HEADER_SYNONYMS: Dict[str, set[str]] = {
    "date": {
        "date",
        "data",
        "transactiondate",
        "transactiondt",
        "dtposted",
        "posteddate",
        "datatransacao",
        "dataoperacao",
        "day",
        "dt",
    },
    "description": {
        "description",
        "descricao",
        "descrica",
        "detalhe",
        "details",
        "memo",
        "name",
        "hist",
        "history",
        "narrativa",
        "desc",
        "payee",
    },
    "amount": {
        "amount",
        "valor",
        "value",
        "quantia",
        "total",
        "ammount",
        "trnamt",
        "montante",
        "valortransacao",
    },
    "type": {
        "type",
        "tipo",
        "transactiontype",
        "trntype",
        "natureza",
        "movimento",
        "movement",
    },
    "account": {
        "account",
        "conta",
        "accountname",
        "accountid",
        "acctid",
        "accountnumber",
        "accnumber",
        "banco",
        "agencia",
    },
    "category": {
        "category",
        "categoria",
        "cat",
        "grupo",
        "group",
        "class",
    },
}

TYPE_ALIASES: Dict[str, str] = {
    "income": "income",
    "receita": "income",
    "entrada": "income",
    "credit": "income",
    "deposit": "income",
    "credito": "income",
    "salary": "income",
    "expense": "expense",
    "despesa": "expense",
    "saida": "expense",
    "debit": "expense",
    "debito": "expense",
    "payment": "expense",
    "compra": "expense",
}

RULE_TYPE_MAP: Dict[str, str] = {
    "debit": "expense",
    "credit": "income",
    "deposit": "income",
    "withdrawal": "expense",
    "payment": "expense",
    "atm": "expense",
}

DATE_FORMATS = [
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%m-%d-%Y",
    "%Y%m%d",
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M:%S",
]


@dataclass
class ParsedTransaction:
    """Internal representation of a parsed transaction line."""

    index: int
    date: Optional[datetime]
    description: str
    amount: float
    transaction_type: str
    account_name: Optional[str]
    category_name: Optional[str]
    warnings: List[str] = field(default_factory=list)
    account_id: Optional[int] = None
    category_id: Optional[int] = None
    override_category_id: Optional[int] = None
    applied_category_id: Optional[int] = None
    normalized_description: str = ""
    source_hash: str = ""
    duplicate: bool = False
    suggested_category_id: Optional[int] = None
    matched_rule_id: Optional[int] = None

    def add_warning(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)


@dataclass
class ParsedFileResult:
    rows: List[ParsedTransaction]
    total_rows: int
    skipped_rows: int
    columns: List[str]
    currency_guess: Optional[str] = None
    detected_account_name: Optional[str] = None


class ImportError(HTTPException):
    """Specialized HTTP exception for import errors."""

    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> None:
        super().__init__(status_code=status_code, detail=detail)


def _normalize_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ASCII", "ignore").decode("ASCII")
    normalized = re.sub(r"[^a-z0-9]", "", normalized.lower())
    return normalized


def _normalize_description(value: str) -> str:
    collapsed = re.sub(r"\s+", " ", value.strip())
    return collapsed.lower()


def _parse_amount(value: str) -> tuple[Optional[float], Optional[str], List[str]]:
    warnings: List[str] = []
    if value is None:
        return None, None, ["Missing amount"]

    cleaned = value.strip()
    if not cleaned:
        return None, None, ["Missing amount"]

    currency: Optional[str] = None
    currency_prefixes = {
        "R$": "BRL",
        "$": "USD",
        "€": "EUR",
        "£": "GBP",
    }
    for prefix, code in currency_prefixes.items():
        if cleaned.startswith(prefix):
            currency = code
            cleaned = cleaned[len(prefix) :].strip()
            break

    alpha_prefix = re.match(r"^([A-Za-z]{3})\s*", cleaned)
    if alpha_prefix:
        currency = alpha_prefix.group(1).upper()
        cleaned = cleaned[alpha_prefix.end() :]

    cleaned = cleaned.replace("R$", "").strip()
    negative = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        negative = True
        cleaned = cleaned[1:-1]
    if cleaned.startswith("-"):
        negative = True
        cleaned = cleaned[1:]
    cleaned = cleaned.replace(" ", "")

    separators = {",", "."}
    comma_count = cleaned.count(",")
    dot_count = cleaned.count(".")

    if comma_count and dot_count:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "")
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif comma_count == 1 and dot_count == 0:
        cleaned = cleaned.replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")

    cleaned = re.sub(r"[^0-9.]", "", cleaned)

    try:
        amount = float(cleaned)
    except ValueError:
        warnings.append(f"Could not parse amount '{value}'.")
        return None, currency, warnings

    if negative:
        amount = -amount

    return amount, currency, warnings


def _parse_type(raw_value: Optional[str], amount: Optional[float]) -> str:
    if raw_value:
        normalized = _normalize_key(raw_value)
        if normalized in TYPE_ALIASES:
            return TYPE_ALIASES[normalized]
    if amount is not None:
        return "expense" if amount < 0 else "income"
    return "expense"


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None

    iso_candidate = raw.replace("Z", "")
    try:
        return datetime.fromisoformat(iso_candidate)
    except ValueError:
        pass

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue

    # OFX style date: YYYYMMDDHHMMSS[.nnn][gmt offset]
    match = re.match(r"^(\d{4})(\d{2})(\d{2})(\d{0,2})(\d{0,2})(\d{0,2})", raw)
    if match:
        year, month, day, hour, minute, second = match.groups()
        hour = hour or "00"
        minute = minute or "00"
        second = second or "00"
        try:
            return datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
        except ValueError:
            return None

    return None


def _build_header_map(headers: Iterable[str], mapping: Optional[dict[str, str]]) -> dict[str, str]:
    header_map: dict[str, str] = {}
    normalized_headers = {_normalize_key(header): header for header in headers if header}

    if mapping:
        for canonical, source in mapping.items():
            if canonical not in CANONICAL_FIELDS or not source:
                continue
            normalized_source = _normalize_key(source)
            if normalized_source in normalized_headers:
                header_map[canonical] = normalized_headers[normalized_source]

    for normalized, original in normalized_headers.items():
        for canonical, synonyms in HEADER_SYNONYMS.items():
            if canonical in header_map:
                continue
            if normalized in synonyms:
                header_map[canonical] = original
                break

    return header_map


def _decode_bytes(data: bytes) -> tuple[str, str]:
    try:
        text = data.decode("utf-8")
        return text, "utf-8"
    except UnicodeDecodeError:
        text = data.decode("latin-1")
        return text, "latin-1"


def _parse_csv(data: bytes, mapping: Optional[dict[str, str]]) -> ParsedFileResult:
    text, _encoding = _decode_bytes(data)
    sample = text[:2048]
    delimiter = ","
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        if dialect.delimiter in {",", ";", "\t"}:
            delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    headers = reader.fieldnames or []
    header_map = _build_header_map(headers, mapping)
    rows: List[ParsedTransaction] = []
    total_rows = 0
    skipped_rows = 0
    currency_guess: Optional[str] = None

    for index, row in enumerate(reader):
        total_rows += 1
        description = row.get(header_map.get("description", ""), "").strip()
        date_value = row.get(header_map.get("date", ""))
        amount_value = row.get(header_map.get("amount", ""))

        amount, detected_currency, amount_warnings = _parse_amount(amount_value)
        date_parsed = _parse_date(date_value)
        transaction_type = _parse_type(row.get(header_map.get("type", "")), amount)
        account_name = row.get(header_map.get("account", "")) or None
        category_name = row.get(header_map.get("category", "")) or None

        if detected_currency and not currency_guess:
            currency_guess = detected_currency

        warnings: List[str] = amount_warnings.copy()
        if not description:
            warnings.append("Missing description")
        if date_value and not date_parsed:
            warnings.append(f"Unrecognized date format '{date_value}'.")
        if amount is None:
            warnings.append("Amount is required")

        if not description or amount is None or date_parsed is None:
            skipped_rows += 1
            continue

        rows.append(
            ParsedTransaction(
                index=index,
                date=date_parsed,
                description=description,
                amount=amount,
                transaction_type=transaction_type,
                account_name=account_name.strip() if isinstance(account_name, str) else account_name,
                category_name=category_name.strip() if isinstance(category_name, str) else category_name,
                warnings=warnings,
            )
        )

    columns = list(header_map.keys())
    return ParsedFileResult(rows=rows, total_rows=total_rows, skipped_rows=skipped_rows, columns=columns, currency_guess=currency_guess)


def _extract_tag(block: str, tag: str) -> Optional[str]:
    pattern = re.compile(rf"<{tag}>([^<\r\n]+)", re.IGNORECASE)
    match = pattern.search(block)
    if match:
        return match.group(1).strip()
    return None


def _parse_ofx(data: bytes) -> ParsedFileResult:
    text, _encoding = _decode_bytes(data)
    currency_guess = _extract_tag(text, "CURDEF")
    account_name = _extract_tag(text, "ACCTID") or _extract_tag(text, "ACCTNAME")

    transactions_blocks = re.split(r"<STMTTRN>", text, flags=re.IGNORECASE)
    rows: List[ParsedTransaction] = []
    total_rows = 0
    skipped_rows = 0

    for index, block in enumerate(transactions_blocks[1:]):
        total_rows += 1
        date_value = _extract_tag(block, "DTPOSTED")
        amount_value = _extract_tag(block, "TRNAMT")
        trn_type = _extract_tag(block, "TRNTYPE")
        name = _extract_tag(block, "NAME")
        memo = _extract_tag(block, "MEMO")

        description_parts = [part for part in [name, memo] if part]
        description = " - ".join(description_parts) if description_parts else (name or memo or "")

        amount, detected_currency, amount_warnings = _parse_amount(amount_value or "")
        if detected_currency and not currency_guess:
            currency_guess = detected_currency

        date_parsed = _parse_date(date_value)
        transaction_type = RULE_TYPE_MAP.get((trn_type or "").lower(), None)
        if not transaction_type:
            transaction_type = _parse_type(trn_type, amount)

        warnings = amount_warnings.copy()
        if not description:
            warnings.append("Missing description")
        if date_value and not date_parsed:
            warnings.append(f"Unrecognized date format '{date_value}'.")
        if amount is None:
            warnings.append("Amount is required")

        if not description or amount is None or date_parsed is None:
            skipped_rows += 1
            continue

        rows.append(
            ParsedTransaction(
                index=index,
                date=date_parsed,
                description=description,
                amount=amount,
                transaction_type=transaction_type,
                account_name=account_name,
                category_name=None,
                warnings=warnings,
            )
        )

    columns = ["date", "description", "amount", "type", "account"]
    return ParsedFileResult(
        rows=rows,
        total_rows=total_rows,
        skipped_rows=skipped_rows,
        columns=columns,
        currency_guess=currency_guess,
        detected_account_name=account_name,
    )


async def _load_user_context(db: AsyncSession, user: User) -> tuple[dict[int, Account], dict[str, Account], dict[int, Category], dict[tuple[str, str], Category], List[Rule]]:
    accounts_result = await db.execute(select(Account).where(Account.user_id == user.id))
    accounts = accounts_result.scalars().all()
    accounts_by_id = {account.id: account for account in accounts}
    accounts_by_name = {_normalize_key(account.name): account for account in accounts}

    categories_result = await db.execute(select(Category).where(Category.user_id == user.id))
    categories = categories_result.scalars().all()
    categories_by_id = {category.id: category for category in categories}
    categories_by_key = {
        (category.type, _normalize_key(category.name)): category for category in categories
    }

    rules_result = await db.execute(
        select(Rule)
        .where(and_(Rule.user_id == user.id, Rule.is_active.is_(True)))
        .order_by(Rule.priority.asc(), Rule.id.asc())
    )
    rules = rules_result.scalars().all()

    return accounts_by_id, accounts_by_name, categories_by_id, categories_by_key, list(rules)


def _compute_source_hash(row: ParsedTransaction) -> None:
    if not row.date or row.account_id is None:
        return
    normalized_description = row.normalized_description or _normalize_description(row.description)
    row.normalized_description = normalized_description
    payload = f"{row.date.isoformat()}|{row.amount}|{normalized_description}|{row.account_id}"
    row.source_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _mark_internal_duplicates(rows: List[ParsedTransaction]) -> None:
    seen: dict[str, ParsedTransaction] = {}
    for row in rows:
        if not row.source_hash:
            continue
        if row.source_hash in seen:
            row.duplicate = True
            row.add_warning("Duplicate transaction detected in file")
        else:
            seen[row.source_hash] = row


async def _mark_duplicates(db: AsyncSession, user: User, rows: List[ParsedTransaction]) -> None:
    hashes = [row.source_hash for row in rows if row.source_hash]
    if not hashes:
        return
    result = await db.execute(
        select(Transaction.source_hash)
        .join(Account, Transaction.account_id == Account.id)
        .where(
            and_(
                Account.user_id == user.id,
                Transaction.source_hash.in_(hashes),
            )
        )
    )
    existing = {value for value in result.scalars() if value}
    for row in rows:
        if row.source_hash and row.source_hash in existing:
            row.duplicate = True
            row.add_warning("Duplicate transaction detected")


def _apply_rules(rows: List[ParsedTransaction], rules: List[Rule]) -> None:
    for row in rows:
        normalized_description = row.normalized_description or _normalize_description(row.description)
        row.normalized_description = normalized_description
        for rule in rules:
            if not rule.match_text:
                continue
            if _normalize_key(rule.match_text) in normalized_description.replace(" ", ""):
                row.suggested_category_id = rule.category_id
                row.matched_rule_id = rule.id
                break


def _resolve_accounts(rows: List[ParsedTransaction], provided_account_id: Optional[int], accounts_by_id: dict[int, Account], accounts_by_name: dict[str, Account], detected_account_name: Optional[str]) -> None:
    detected_account = None
    if detected_account_name:
        detected_account = accounts_by_name.get(_normalize_key(detected_account_name))

    for row in rows:
        if provided_account_id is not None and provided_account_id in accounts_by_id:
            account = accounts_by_id[provided_account_id]
            row.account_id = account.id
            row.account_name = account.name
        elif row.account_name:
            key = _normalize_key(row.account_name)
            account = accounts_by_name.get(key)
            if account:
                row.account_id = account.id
                row.account_name = account.name
            else:
                row.add_warning(f"Account '{row.account_name}' not found for user")
        elif detected_account:
            row.account_id = detected_account.id
            row.account_name = detected_account.name
        else:
            row.add_warning("Account could not be resolved")

        _compute_source_hash(row)


def _resolve_categories(rows: List[ParsedTransaction], categories_by_id: dict[int, Category], categories_by_key: dict[tuple[str, str], Category]) -> None:
    for row in rows:
        if row.category_id:
            continue
        matched: Optional[Category] = None
        if row.category_name:
            key = _normalize_key(row.category_name)
            matched = categories_by_key.get((row.transaction_type, key))
            if not matched:
                # fallback ignoring type
                for (cat_type, cat_key), category in categories_by_key.items():
                    if cat_key == key:
                        matched = category
                        break
        if matched:
            row.category_id = matched.id
            row.category_name = matched.name
        elif row.category_id in categories_by_id:
            row.category_name = categories_by_id[row.category_id].name


def _apply_overrides(rows: List[ParsedTransaction], overrides: Optional[dict[str, int]]) -> None:
    if not overrides:
        return
    for row in rows:
        if row.source_hash and row.source_hash in overrides:
            row.override_category_id = overrides[row.source_hash]


def _finalize_category_selection(rows: List[ParsedTransaction], categories_by_id: dict[int, Category]) -> None:
    for row in rows:
        chosen_id = row.override_category_id or row.category_id or row.suggested_category_id
        if chosen_id and chosen_id in categories_by_id:
            row.applied_category_id = chosen_id
            row.category_name = categories_by_id[chosen_id].name
        else:
            if row.override_category_id and row.override_category_id not in categories_by_id:
                row.add_warning("Override category is not available for this user")
            row.applied_category_id = None


def _build_preview_response(result: ParsedFileResult, rows: List[ParsedTransaction]) -> ImportPreviewResponse:
    preview_items = [
        ImportPreviewItem(
            index=row.index,
            date=row.date,
            description=row.description,
            amount=row.amount,
            transaction_type=row.transaction_type,
            account_id=row.account_id,
            account_name=row.account_name,
            category_id=row.applied_category_id,
            category_name=row.category_name,
            suggested_category_id=row.suggested_category_id,
            matched_rule_id=row.matched_rule_id,
            source_hash=row.source_hash,
            duplicate=row.duplicate,
            warnings=row.warnings,
        )
        for row in rows
    ]

    summary = ImportSummary(
        total_rows=result.total_rows,
        parsed_rows=len(rows),
        skipped_rows=result.skipped_rows,
        currency_guess=result.currency_guess,
    )

    return ImportPreviewResponse(summary=summary, columns=result.columns, items=preview_items)


async def process_import(
    *,
    db: AsyncSession,
    user: User,
    filename: str,
    file_bytes: bytes,
    mode: ImportMode,
    mapping: Optional[dict[str, str]] = None,
    provided_account_id: Optional[int] = None,
    overrides: Optional[dict[str, int]] = None,
    save_rules: bool = False,
) -> ImportPreviewResponse | ImportApplyResponse:
    """Process a CSV or OFX import request."""

    if len(file_bytes) > MAX_FILE_BYTES:
        raise ImportError(
            detail=f"File exceeds maximum allowed size of {settings.IMPORT_MAX_FILE_MB} MB."
        )

    extension_match = re.search(r"(\.[A-Za-z0-9]+)$", filename)
    extension = extension_match.group(1).lower() if extension_match else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise ImportError("Unsupported file type. Upload a CSV or OFX file.")

    mapping_dict = mapping or {}

    if provided_account_id is not None:
        account_check = await db.execute(
            select(Account).where(Account.id == provided_account_id, Account.user_id == user.id)
        )
        if not account_check.scalar_one_or_none():
            raise ImportError("Account not found for the current user.", status.HTTP_404_NOT_FOUND)

    if extension == ".csv":
        parsed_result = _parse_csv(file_bytes, mapping_dict)
    else:
        parsed_result = _parse_ofx(file_bytes)

    (
        accounts_by_id,
        accounts_by_name,
        categories_by_id,
        categories_by_key,
        rules,
    ) = await _load_user_context(db, user)

    _resolve_accounts(
        parsed_result.rows,
        provided_account_id,
        accounts_by_id,
        accounts_by_name,
        parsed_result.detected_account_name,
    )
    _resolve_categories(parsed_result.rows, categories_by_id, categories_by_key)
    _apply_overrides(parsed_result.rows, overrides)
    _apply_rules(parsed_result.rows, rules)
    _finalize_category_selection(parsed_result.rows, categories_by_id)
    _mark_internal_duplicates(parsed_result.rows)
    await _mark_duplicates(db, user, parsed_result.rows)

    if mode == ImportMode.PREVIEW:
        return _build_preview_response(parsed_result, parsed_result.rows)

    # Apply mode
    inserted = 0
    duplicates = 0
    failed = 0
    for row in parsed_result.rows:
        if not row.date or row.account_id is None:
            row.add_warning("Missing required data for insertion")
            failed += 1
            continue
        if row.duplicate:
            duplicates += 1
            continue

        category_id = row.applied_category_id
        if category_id and category_id not in categories_by_id:
            row.add_warning("Invalid category selection")
            failed += 1
            continue

        transaction = Transaction(
            account_id=row.account_id,
            amount=row.amount,
            transaction_type=row.transaction_type,
            description=row.description,
            transaction_date=row.date,
            category_id=category_id,
            category=categories_by_id[category_id].name if category_id else None,
            source_hash=row.source_hash or None,
        )
        db.add(transaction)
        inserted += 1

    await db.flush()

    created_rules = 0
    updated_rules = 0
    if save_rules and overrides:
        for row in parsed_result.rows:
            if not row.override_category_id:
                continue
            category_id = row.override_category_id
            if not category_id or category_id not in categories_by_id:
                continue
            normalized_description = row.normalized_description or _normalize_description(row.description)
            rule_lookup = await db.execute(
                select(Rule).where(
                    Rule.user_id == user.id,
                    Rule.match_text == row.description,
                )
            )
            rule = rule_lookup.scalar_one_or_none()
            if rule:
                if rule.category_id != category_id:
                    rule.category_id = category_id
                    updated_rules += 1
            else:
                new_rule = Rule(
                    user_id=user.id,
                    match_text=row.description,
                    category_id=category_id,
                )
                db.add(new_rule)
                created_rules += 1

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return ImportApplyResponse(
        inserted=inserted,
        duplicates=duplicates,
        failed=failed,
        created_rules=created_rules,
        updated_rules=updated_rules,
    )
