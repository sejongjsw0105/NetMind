from __future__ import annotations

import glob
import json
import os
import subprocess
from pathlib import Path
from typing import List

from .config import YosysConfig
from .utils import win_to_wsl_path


def collect_hdl_files(src_dir_win: str) -> List[str]:
    verilog_files = glob.glob(os.path.join(src_dir_win, "*.v"))
    sv_files = glob.glob(os.path.join(src_dir_win, "*.sv"))
    return verilog_files + sv_files


def build_yosys_script(files_wsl: List[str], top_module: str, out_json_wsl: str) -> str:
    return "\n".join(
        [
            f"read_verilog -sv {' '.join(files_wsl)};",
            f"hierarchy -check -top {top_module};",
            "proc;",
            "opt;",
            f"write_json {out_json_wsl}",
        ]
    )


def run_yosys(files_win: List[str], config: YosysConfig) -> None:
    if not files_win:
        raise RuntimeError("No HDL files found.")

    files_wsl = [win_to_wsl_path(f) for f in files_win]
    out_json_wsl = win_to_wsl_path(config.out_json_win)
    yosys_script = build_yosys_script(files_wsl, config.top_module, out_json_wsl)

    subprocess.run(["wsl", "yosys", "-p", yosys_script], check=True)


def load_yosys_json(out_json_win: str) -> dict:
    with open(out_json_win, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_yosys(config: YosysConfig) -> dict:
    files_win = collect_hdl_files(config.src_dir_win)
    run_yosys(files_win, config)
    return load_yosys_json(config.out_json_win)
