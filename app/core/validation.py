from typing import Optional, Tuple, List
import re
from fastapi import HTTPException


def parse_money(value: Optional[str]) -> Tuple[float, List[str]]:
    """Parse a user-provided monetary string into a float.

    Accepts formats like:
      - "1234.56"
      - "1,234.56"
      - "1.234,56" (common in pt-BR)
      - "R$ 1.234,56"
      - "(1,234.56)" -> negative

    Returns (amount, warnings). Raises HTTPException on clearly invalid input.
    """
    warnings: List[str] = []
    if value is None:
        raise HTTPException(status_code=400, detail="Amount is required")

    s = str(value).strip()
    if s == "":
        raise HTTPException(status_code=400, detail="Amount is required")

    # remove currency symbols and surrounding whitespace
    s = re.sub(r"[R$€£¥ ]", "", s)

    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    if s.startswith("-"):
        negative = True
        s = s[1:]

    # normalize separators: if both '.' and ',' present, assume '.' is thousands
    # and ',' is decimal when the last separator is a comma
    comma_count = s.count(',')
    dot_count = s.count('.')
    if comma_count and dot_count:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '')
            s = s.replace(',', '.')
        else:
            s = s.replace(',', '')
    elif comma_count == 1 and dot_count == 0:
        s = s.replace(',', '.')
    else:
        s = s.replace(',', '')

    # strip anything that's not digit or dot
    s = re.sub(r"[^0-9.]", "", s)

    if s == "":
        raise HTTPException(status_code=400, detail="Invalid amount")

    try:
        amount = float(s)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Could not parse amount '{value}'")

    if negative:
        amount = -amount

    return amount, warnings
