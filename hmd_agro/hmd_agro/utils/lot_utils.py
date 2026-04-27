"""Shared utilities for lot-related logic."""

import re


def lot_sort_key(name):
    """Sort lots in production-cycle order:
    LOT1..LOTn (numeric) → TARISSEMENT → TARIE → INFIRMERIE → others (alphabetical).
    """
    name = (name or "").upper()
    m = re.match(r"^LOT(\d+)$", name)
    if m:
        return (0, int(m.group(1)))
    if name == "TARISSEMENT":
        return (1, 0)
    if name == "TARIE":
        return (2, 0)
    if name == "INFIRMERIE":
        return (3, 0)
    return (4, name)
