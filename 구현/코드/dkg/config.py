from __future__ import annotations

from dataclasses import dataclass


@dataclass
class YosysConfig:
    src_dir_win: str
    out_json_win: str
    top_module: str
