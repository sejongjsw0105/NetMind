from dataclasses import dataclass
from typing import Optional
@dataclass
class GraphVersion:
    rtl_hash: str
    constraint_hash: Optional[str]
    timing_hash: Optional[str]
    policy_versions: dict
# 캐싱을 위한 그래프 버전 정보
# TODO: 향후 그래프 구성 요소별 해시 추가 고려