"""CSV detector + tokenizer — port of lib/import/csv-detector.ts."""

from __future__ import annotations

import re
from typing import Any

BOM_UTF8 = "﻿"
CANDIDATE_DELIMITERS = [";", ",", "\t", "|"]


def strip_bom(content: str) -> tuple[str, bool]:
    if content.startswith(BOM_UTF8):
        return content[1:], True
    return content, False


def detect_delimiter(sample_lines: list[str]) -> str:
    lines = [l for l in sample_lines[:10] if l.strip()]
    if not lines:
        return ";"
    best_delim = ";"
    best_score = float("-inf")
    for delim in CANDIDATE_DELIMITERS:
        counts = [len(l.split(delim)) for l in lines]
        mean = sum(counts) / len(counts)
        if mean < 2:
            continue
        variance = sum((c - mean) ** 2 for c in counts) / len(counts)
        score = mean - variance * 2
        if score > best_score:
            best_score = score
            best_delim = delim
    return best_delim


def detect_decimal_separator(values: list[str]) -> str:
    comma = dot = 0
    for v in values:
        s = v.strip()
        if not s:
            continue
        if re.match(r"^[-+]?[\d.]*,\d{1,4}$", s):
            comma += 1
        elif re.match(r"^[-+]?[\d,]*\.\d{1,4}$", s):
            dot += 1
        elif re.match(r"^[-+]?\d+,\d{1,4}$", s):
            comma += 1
        elif re.match(r"^[-+]?\d+\.\d{1,4}$", s):
            dot += 1
    return "," if comma >= dot else "."


def detect_date_format(values: list[str]) -> str:
    samples = [v.strip() for v in values if v.strip()][:30]
    dot_dmy = iso_ymd = 0
    slash_ambiguous: list[tuple[int, int]] = []
    for s in samples:
        if re.match(r"^\d{2}\.\d{2}\.\d{4}(\s|$)", s):
            dot_dmy += 1
        elif re.match(r"^\d{4}-\d{2}-\d{2}(\s|$)", s):
            iso_ymd += 1
        else:
            m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", s)
            if m:
                slash_ambiguous.append((int(m.group(1)), int(m.group(2))))
    if dot_dmy >= iso_ymd and dot_dmy >= len(slash_ambiguous):
        return "dd.MM.yyyy"
    if iso_ymd >= len(slash_ambiguous):
        return "yyyy-MM-dd"
    if slash_ambiguous:
        day_first = any(a > 12 for a, _ in slash_ambiguous)
        month_first = any(b > 12 for _, b in slash_ambiguous)
        if day_first and not month_first:
            return "dd/MM/yyyy"
        if month_first and not day_first:
            return "MM/dd/yyyy"
        return "MM/dd/yyyy"
    return "dd.MM.yyyy"


def detect_header_row(rows: list[list[str]]) -> tuple[int, int]:
    for i in range(min(len(rows), 20)):
        row = rows[i]
        non_empty = [c for c in row if c.strip()]
        if len(non_empty) < 3:
            continue
        textual = [c for c in non_empty if re.search(r"[a-zA-ZäöüÄÖÜß]{2,}", c)]
        if len(textual) / len(non_empty) >= 0.6:
            return i + 1, i
    return 1, 0


def tokenize_csv_line(line: str, delimiter: str, quote_char: str = '"') -> list[str]:
    out: list[str] = []
    cur = ""
    in_quotes = False
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if in_quotes:
            if ch == quote_char:
                if i + 1 < n and line[i + 1] == quote_char:
                    cur += quote_char
                    i += 1
                else:
                    in_quotes = False
            else:
                cur += ch
        else:
            if ch == quote_char:
                in_quotes = True
            elif line.startswith(delimiter, i):
                out.append(cur)
                cur = ""
                i += len(delimiter) - 1
            else:
                cur += ch
        i += 1
    out.append(cur)
    return out


def auto_detect(raw_content: str) -> dict[str, Any]:
    content, has_bom = strip_bom(raw_content)
    all_lines = re.split(r"\r?\n", content)
    sample = [l for l in all_lines[:30] if l]
    delimiter = detect_delimiter(sample)
    parsed_rows = [tokenize_csv_line(l, delimiter) for l in all_lines[:50] if l]
    header_row, skip_rows = detect_header_row(parsed_rows)
    header = parsed_rows[header_row - 1] if header_row - 1 < len(parsed_rows) else []
    data_rows = parsed_rows[header_row:]

    def column_values(col: int) -> list[str]:
        return [r[col] for r in data_rows if col < len(r) and r[col].strip()]

    decimal_separator = ","
    best_numeric = 0
    for col in range(len(header)):
        vals = column_values(col)
        numeric_like = [v for v in vals if re.search(r"\d", v) and re.search(r"[.,]", v)]
        if len(numeric_like) > best_numeric:
            best_numeric = len(numeric_like)
            decimal_separator = detect_decimal_separator(numeric_like)

    date_format = "dd.MM.yyyy"
    best_date = 0
    for col in range(len(header)):
        vals = column_values(col)
        date_like = [v for v in vals if re.search(r"\d{1,4}[./-]\d{1,2}[./-]\d{1,4}", v)]
        if len(date_like) > best_date:
            best_date = len(date_like)
            date_format = detect_date_format(date_like)

    return {
        "delimiter": delimiter,
        "encoding": "utf-8-sig" if has_bom else "utf-8",
        "decimalSeparator": decimal_separator,
        "dateFormat": date_format,
        "headerRow": header_row,
        "skipRows": skip_rows,
        "header": header,
        "confidence": min(1, best_numeric / 10) * 0.5 + min(1, best_date / 10) * 0.5,
    }
