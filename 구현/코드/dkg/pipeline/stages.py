from __future__ import annotations

from enum import Enum
from typing import FrozenSet


class ParsingStage(str, Enum):
    """파싱 단계 정의. 순서대로 실행됨."""
    
    RTL = "rtl"                    # Yosys JSON (구조 정보)
    SYNTHESIS = "synthesis"        # 합성 후 netlist
    CONSTRAINTS = "constraints"    # SDC/XDC (타이밍/클럭 제약)
    FLOORPLAN = "floorplan"        # TCL/Pblock (물리적 배치)
    TIMING = "timing"              # 타이밍 리포트
    BOARD = "board"                # BD/board constraints


class FieldSource(str, Enum):
    """필드 값의 출처"""
    
    INFERRED = "inferred"          # 휴리스틱으로 추론
    DECLARED = "declared"          # 명시적으로 선언됨
    ANALYZED = "analyzed"          # 도구 분석 결과
    USER_OVERRIDE = "user_override"  # 사용자 직접 설정


# 각 필드가 어느 stage에서 확정되는지 정의
FIELD_STAGES: dict[str, FrozenSet[ParsingStage]] = {
    # Node fields
    "entity_class": frozenset([ParsingStage.RTL, ParsingStage.SYNTHESIS]),
    "hier_path": frozenset([ParsingStage.RTL, ParsingStage.SYNTHESIS]),
    "clock_domain": frozenset([ParsingStage.RTL, ParsingStage.CONSTRAINTS]),
    "arrival_time": frozenset([ParsingStage.TIMING]),
    "required_time": frozenset([ParsingStage.TIMING]),
    "slack": frozenset([ParsingStage.TIMING]),
    
    # Edge fields
    "signal_name": frozenset([ParsingStage.RTL, ParsingStage.SYNTHESIS]),
    "flow_type": frozenset([ParsingStage.RTL, ParsingStage.CONSTRAINTS]),
    "clock_signal": frozenset([ParsingStage.CONSTRAINTS]),
    "reset_signal": frozenset([ParsingStage.CONSTRAINTS]),
    "delay": frozenset([ParsingStage.TIMING]),
    "timing_exception": frozenset([ParsingStage.CONSTRAINTS]),
}


def get_priority(source: FieldSource) -> int:
    """값 우선순위. 높을수록 신뢰도 높음."""
    priorities = {
        FieldSource.INFERRED: 1,
        FieldSource.DECLARED: 3,
        FieldSource.ANALYZED: 2,
        FieldSource.USER_OVERRIDE: 4,
    }
    return priorities[source]


def should_update_field(
    current_source: FieldSource | None,
    new_source: FieldSource,
) -> bool:
    """기존 값을 새 값으로 업데이트할지 결정"""
    if current_source is None:
        return True
    return get_priority(new_source) >= get_priority(current_source)
