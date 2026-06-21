"""Rule inference — port of lib/rule-inference.ts.

Infers a likely BookingRule from a selected set of transactions: common
auftraggeber pattern (search-hint → longest common prefix → frequent non-stopword
→ frequent word) + most-frequent kostenbereich (≥50%).
"""

from __future__ import annotations

import math
import re
from typing import Any

STOPWORDS = {
    "gmbh", "ag", "kg", "ohg", "ev", "evv",
    "gemeinnuetzige", "gemeinnutzige", "gemeinnützige",
    "deutsche", "deutscher", "deutschland",
    "online", "international", "europe",
    "the", "der", "die", "das", "und",
    "co", "kgaa", "se",
}

_WORD_SPLIT = re.compile(r"[\s,./\-]+")


def infer_auftraggeber_pattern(
    strings: list[str | None], search_hint: str | None = None
) -> tuple[str | None, bool]:
    cleaned = [s.strip() for s in strings if s and s.strip()]
    if not cleaned:
        return None, False
    if len(cleaned) == 1:
        return cleaned[0], True
    if all(s.lower() == cleaned[0].lower() for s in cleaned):
        return cleaned[0], True

    lower = [s.lower() for s in cleaned]
    threshold = math.ceil(len(cleaned) * 0.8)

    if search_hint and len(search_hint.strip()) >= 3:
        hint = search_hint.strip().lower()
        if sum(1 for s in lower if hint in s) >= threshold:
            return search_hint.strip(), False

    # longest common prefix
    prefix = lower[0]
    for s in lower[1:]:
        while prefix and not s.startswith(prefix):
            prefix = prefix[:-1]
        if not prefix:
            break
    prefix = prefix.strip()
    if len(prefix) >= 4:
        return prefix, False

    # word frequency
    presence: dict[str, int] = {}
    for s in lower:
        words = {w for w in _WORD_SPLIT.split(s) if len(w) >= 3}
        for w in words:
            presence[w] = presence.get(w, 0) + 1
    candidates = sorted(
        [(w, c) for w, c in presence.items() if c >= threshold],
        key=lambda x: (-x[1], -len(x[0])),
    )
    non_stop = next((c for c in candidates if c[0] not in STOPWORDS), None)
    if non_stop:
        return non_stop[0], False
    if candidates:
        return candidates[0][0], False
    return None, False


def infer_most_frequent_kostenbereich(kb_ids: list[str | None]) -> str | None:
    counts: dict[str, int] = {}
    total = 0
    for kid in kb_ids:
        if not kid:
            continue
        counts[kid] = counts.get(kid, 0) + 1
        total += 1
    if total == 0:
        return None
    top = max(counts.items(), key=lambda x: x[1])
    return top[0] if top[1] / total >= 0.5 else None


def infer_rule(transactions: list[dict[str, Any]], search_hint: str | None = None) -> dict[str, Any]:
    pattern, exact = infer_auftraggeber_pattern(
        [t.get("auftraggeber") for t in transactions], search_hint
    )
    kb_id = infer_most_frequent_kostenbereich([t.get("kostenbereich_id") for t in transactions])
    return {
        "match_auftraggeber": pattern,
        "match_auftraggeber_exact": exact,
        "match_kostenbereich_id": kb_id,
    }
