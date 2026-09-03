"""Helpers for writing CSV safely.

Spreadsheet apps (Excel, Google Sheets, LibreOffice) treat a cell whose text
starts with '=', '+', '-', '@', or certain control characters as a *formula*.
Because we export Reddit-derived text (post titles, flair, etc.), a crafted
value like ``=HYPERLINK(...)`` could execute when the exported file is opened.
`csv_safe` neutralizes that by prefixing such values with a single quote.
"""

_RISKY_PREFIXES = ('=', '+', '-', '@', '\t', '\r', '\n')


def csv_safe(value):
    """Return `value` neutralized against CSV/formula injection.

    Non-string values (e.g. int scores) are returned unchanged."""
    if isinstance(value, str) and value[:1] in _RISKY_PREFIXES:
        return "'" + value
    return value


def safe_row(row):
    """Apply :func:`csv_safe` to every cell in an iterable row."""
    return [csv_safe(cell) for cell in row]
