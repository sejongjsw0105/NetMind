from __future__ import annotations

import re
from typing import Iterable, List


def _split_target_list(raw: str) -> List[str]:
    text = raw.strip()
    if text.startswith("{") and text.endswith("}"):
        text = text[1:-1].strip()
    parts = re.split(r"\s+", text)
    return [p.strip('"') for p in parts if p.strip('"')]


def extract_bracket_targets(line: str, object_types: Iterable[str]) -> List[str]:
    targets: List[str] = []
    pattern = r"\[get_(%s)\s+([^\]]+)\]" % "|".join(object_types)
    for match in re.finditer(pattern, line):
        targets.extend(_split_target_list(match.group(2)))
    return targets


def extract_option_targets(line: str, option: str, object_types: Iterable[str]) -> List[str]:
    targets: List[str] = []
    pattern = r"%s\s+\[get_(%s)\s+([^\]]+)\]" % (re.escape(option), "|".join(object_types))
    for match in re.finditer(pattern, line):
        targets.extend(_split_target_list(match.group(2)))
    return targets


def pattern_match(pattern: str, candidate: str) -> bool:
    if not pattern:
        return False
    if "*" not in pattern and "?" not in pattern:
        if pattern == candidate:
            return True
        if pattern in candidate or candidate in pattern:
            return True
    escaped = re.escape(pattern)
    escaped = escaped.replace(r"\*", ".*").replace(r"\?", ".")
    regex = re.compile(r"^%s$" % escaped)
    return bool(regex.match(candidate))


def match_any(patterns: Iterable[str], candidates: Iterable[str]) -> bool:
    for pattern in patterns:
        for cand in candidates:
            if cand and pattern_match(pattern, cand):
                return True
    return False
