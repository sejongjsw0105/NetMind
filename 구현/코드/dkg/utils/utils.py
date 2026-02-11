from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Optional, Tuple


def is_clock_name(name: str) -> bool:
    n = name.lower()
    return n == "clk" or n.startswith("clk") or n.endswith("_clk") or "clock" in n


def is_reset_name(name: str) -> bool:
    n = name.lower()
    return n == "rst" or n.startswith("rst") or n.startswith("reset")


def is_active_low(name: str) -> bool:
    return name.lower().endswith("_n")


def is_ff_cell(cell_type: str) -> bool:
    return cell_type in {"$dff", "$adff", "$sdff", "$dffe", "$sdffe"}


def is_async_reset_ff(cell_type: str) -> bool:
    return cell_type == "$adff"


def is_sync_reset_ff(cell_type: str) -> bool:
    return cell_type == "$sdff"


def win_to_wsl_path(win_path: str) -> str:
    p = Path(win_path).resolve()
    drive = p.drive[0].lower()
    path_no_drive = p.as_posix()[2:]
    return f"/mnt/{drive}{path_no_drive}"


def parse_src(src_str: Optional[str]) -> Tuple[Optional[str], Optional[int]]:
    if not src_str:
        return None, None
    try:
        file_part, line_part = src_str.split(":")
        line = int(line_part.split(".")[0])
        return file_part, line
    except Exception:
        return None, None


def split_signal_bit(sig: str) -> Tuple[str, Optional[int]]:
    m = re.match(r"(.+)\[(\d+)\]$", sig)
    if m:
        return m.group(1), int(m.group(2))
    return sig, None


def stable_hash(s: str, length: int = 12) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:length]


def compute_file_hash(filepath: str | Path) -> str:
    """파일 내용의 SHA-256 해시 계산"""
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()[:16]  # 처음 16자만 사용
