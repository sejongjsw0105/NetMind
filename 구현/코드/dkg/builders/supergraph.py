from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from ..core.graph import DKGEdge, DKGNode, EdgeFlowType, EntityClass, RelationType
from ..core.provenance import Provenance
from ..utils import stable_hash


# ============================================================================
# Analysis Attachment Model
# ============================================================================
# Analysis는 그래프 구조를 변경하지 않는 immutable snapshot이며
# SuperNode/SuperEdge에 keyed bundle로 부착됩니다.
# ============================================================================
class AnalysisKind(str, Enum):
    TIMING = "timing"
    AREA = "area"
    POWER = "power"

@dataclass(frozen=True)
class TimingNodeMetrics:
    """
    SuperNode에 부착되는 Timing 분석 결과.
    
    원칙:
    - 집계 가능한 통계 정보만 포함
    - critical path 여부, slack region 등의 단언 금지
    - path membership 정보 포함 금지
    """
    # 필수 Metrics
    min_slack: float              # 절대 최악값
    p5_slack: float               # tail risk 지표 (5th percentile)
    max_arrival_time: float       # 가장 늦은 도착 시간
    min_required_time: float      # 가장 타이트한 요구 시간
    critical_node_ratio: float    # slack < threshold 비율
    near_critical_ratio: float    # slack < α·clock 비율
    
    # 선택적 Metric
    timing_risk_score: Optional[float] = None  # UI/Alert용 단일 스칼라


@dataclass(frozen=True)
class TimingEdgeMetrics:
    """
    SuperEdge에 부착되는 Timing 분석 결과.
    
    원칙:
    - 지연 특성의 통계만 제공
    - "이 edge가 slack을 결정한다" 등의 단언 금지
    - critical edge 여부 표현 금지
    """
    # 필수 Metrics
    max_delay: float
    p95_delay: float              # 95th percentile delay
    flow_type_histogram: Dict[EdgeFlowType, int]  # comb / seq 비율
    
    # 선택적 Metrics
    fanout_max: Optional[int] = None
    fanout_p95: Optional[float] = None


# ============================================================================
# 그래프 외부 Timing 정보 (필수 분리 대상)
# ============================================================================
# Timing 분석 결과 중 alert, finding, summary, path digest는
# 그래프 외부 객체로 관리하며 그래프와 재결합하지 않습니다.
# ============================================================================


class TimingAlertSeverity(str, Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


@dataclass
class TimingAlert:
    """
    Timing 분석에서 발견된 Alert/Finding.
    
    그래프 외부 객체로 관리되며, entity_ref를 통해 참조만 수행.
    """
    entity_ref: str               # node_id / supernode_id / edge_id
    entity_type: str              # "node" / "supernode" / "edge"
    severity: TimingAlertSeverity
    reason: str
    metrics_snapshot: Dict[str, Any]  # 발견 시점의 metric 사본


@dataclass
class TimingSummary:
    """
    전체 Timing 분석의 요약 정보.
    
    그래프와 독립적으로 관리되는 분석 결과 요약.
    """
    worst_slack: float
    violation_count: int
    near_critical_count: int
    clock_period: float
    analysis_mode: str            # "setup" / "hold" / "both"
    timestamp: Optional[str] = None


@dataclass
class CriticalPathDigest:
    """
    Critical Path의 참조용 Digest (선택적).
    
    Path digest는 참조용이며 그래프와 재결합하지 않습니다.
    UI/Query 계층에서만 사용됩니다.
    """
    path_id: str
    startpoint: str
    endpoint: str
    total_delay: float
    slack: float
    node_sequence: Optional[List[str]] = None  # 참조용


class GraphViewType(str, Enum):
    Structural = "Structural"
    Connectivity = "Connectivity"
    Physical = "Physical"


class GraphContext(str, Enum):
    """
    그래프 생성 및 뷰 선택의 사용 맥락 정의.
    
    - DESIGN:      합성, 구현, 타이밍 분석 (물리적 실체 중심)
    - SIMULATION:  동작 검증, 테스트벤치 (검증 환경 중심)
    """
    DESIGN = "design"
    SIMULATION = "simulation"


class SuperClass(str, Enum):
    ATOMIC = "Atomic"
    MODULE_CLUSTER = "ModuleCluster"
    SEQ_CHAIN = "SequentialChain"
    COMB_CLOUD = "CombinationalCloud"
    IO_CLUSTER = "IOCluster"
    CONSTRAINT_GROUP = "ConstraintGroup"
    ELIMINATED = "EliminatedNode" # superedge로 환원되지 않는 노드의 보존적 표현


class NodeAction(Enum):
    PROMOTE = "promote"
    MERGE = "merge"
    ELIMINATE = "eliminate"


@dataclass
class SuperNode:
    node_id: str
    super_class: SuperClass
    member_nodes: Set[str]
    member_edges: Set[str]
    aggregated_attrs: Dict[str, Any] = field(default_factory=dict)
    provenances: List[Provenance] = field(default_factory=list)
    canonical_name: Optional[str] = None
    display_name: Optional[str] = None
    # Analysis Attachment: keyed bundle for extensibility
    analysis: Dict[AnalysisKind, Any] = field(default_factory=dict, repr=False)
    # analysis dict itself is mutable,
    # but each analysis bundle MUST be immutable snapshot

# superedge는 DKGEdge와 달리 고유한 의미를 가지지 않고 그래프적 연결성을 나타내는 용도. 의미는 멤버 엣지들이 담당
@dataclass
class SuperEdge:
    edge_id: str
    src_node: str
    dst_node: str
    member_edges: Set[str]
    member_nodes: Set[str]
    relation_types: Set[RelationType]
    flow_types: Set[EdgeFlowType]
    provenances: List[Provenance] = field(default_factory=list)
    canonical_name: Optional[str] = None
    display_name: Optional[str] = None
    # Analysis Attachment: keyed bundle for extensibility
    analysis: Dict[AnalysisKind, Any] = field(default_factory=dict, repr=False)
    # analysis dict itself is mutable,
    # but each analysis bundle MUST be immutable snapshot



@dataclass
class SuperGraph:
    super_nodes: Dict[str, SuperNode]
    super_edges: Dict[Tuple[str, str], SuperEdge]
    node_to_super: Dict[str, str]


def make_supernode_canonical_name(sn: SuperNode, nodes: Dict[str, DKGNode]) -> str:
    any_node = nodes[next(iter(sn.member_nodes))]
    base = any_node.hier_path
    return f"{base} : {sn.super_class.value}"


def make_supernode_display_name(sn: SuperNode) -> str:
    if sn.super_class == SuperClass.COMB_CLOUD:
        return "Combinational Logic"
    if sn.super_class == SuperClass.SEQ_CHAIN:
        return "Sequential Chain"
    if sn.super_class == SuperClass.ATOMIC:
        return "Block"
    if sn.super_class == SuperClass.ELIMINATED:
        return "Collapsed"
    return sn.super_class.value


def make_superedge_canonical_name(se: SuperEdge, super_nodes: Dict[str, SuperNode]) -> str:
    src = super_nodes[se.src_node].canonical_name
    dst = super_nodes[se.dst_node].canonical_name
    return f"{src} -> {dst}"


def make_superedge_display_name(se: SuperEdge) -> str:
    if len(se.relation_types) == 1:
        return next(iter(se.relation_types)).value.replace("Relation", "")
    return "Multiple Signals"


def supernode_signature(
    view: GraphViewType,
    super_class: SuperClass,
    member_node_ids: set[str],
    policy_version: str = "v1",
) -> str:
    nodes_part = ",".join(sorted(member_node_ids))
    return "|".join([view.value, super_class.value, policy_version, nodes_part])


def make_supernode_id(
    view: GraphViewType,
    super_class: SuperClass,
    member_node_ids: set[str],
    policy_version: str = "v1",
) -> str:
    sig = supernode_signature(view, super_class, member_node_ids, policy_version)
    h = stable_hash(sig)
    return f"SN_{view.value}_{super_class.value}_{h}"


def superedge_signature(
    src_sn: str,
    dst_sn: str,
    member_edge_ids: set[str],
    policy_version: str = "v1",
) -> str:
    edges_part = ",".join(sorted(member_edge_ids))
    return "|".join([src_sn, dst_sn, policy_version, edges_part])


def make_superedge_id(
    src_sn: str,
    dst_sn: str,
    member_edge_ids: set[str],
    policy_version: str = "v1",
) -> str:
    sig = superedge_signature(src_sn, dst_sn, member_edge_ids, policy_version)
    h = stable_hash(sig)
    return f"SE_{h}"

@dataclass(frozen=True)
class NodePolicy:
    action: NodeAction
    super_class: Optional[SuperClass]  # PROMOTE면 None 가능


# ============================================================================
# POLICY_MAP_DESIGN: 합성/구현/타이밍 분석용 정책
# ============================================================================
# 목표: 실제 칩(FPGA/ASIC)에 배치되는 물리적 실체만 보존
# 핵심 철학: "실제 하드웨어는 무엇인가?"
# ============================================================================
POLICY_MAP_DESIGN: dict[GraphViewType, dict[EntityClass, NodePolicy]] = {

    GraphViewType.Structural: {
        EntityClass.MODULE_INSTANCE: NodePolicy(NodeAction.PROMOTE, SuperClass.ATOMIC),
        EntityClass.IO_PORT:        NodePolicy(NodeAction.PROMOTE, SuperClass.ATOMIC),

        EntityClass.RTL_BLOCK:      NodePolicy(NodeAction.MERGE, SuperClass.MODULE_CLUSTER),
        EntityClass.FSM:            NodePolicy(NodeAction.MERGE, SuperClass.MODULE_CLUSTER),
        EntityClass.FLIP_FLOP:      NodePolicy(NodeAction.MERGE, SuperClass.MODULE_CLUSTER),
        EntityClass.LUT:            NodePolicy(NodeAction.MERGE, SuperClass.MODULE_CLUSTER),
        EntityClass.MUX:            NodePolicy(NodeAction.MERGE, SuperClass.MODULE_CLUSTER),
        EntityClass.DSP:            NodePolicy(NodeAction.MERGE, SuperClass.MODULE_CLUSTER),
        EntityClass.BRAM:           NodePolicy(NodeAction.MERGE, SuperClass.MODULE_CLUSTER),

        EntityClass.PACKAGE_PIN:    NodePolicy(NodeAction.ELIMINATE, SuperClass.ELIMINATED),
        EntityClass.PBLOCK:         NodePolicy(NodeAction.ELIMINATE, SuperClass.ELIMINATED),
        EntityClass.BOARD_CONNECTOR:NodePolicy(NodeAction.ELIMINATE, SuperClass.ELIMINATED),
    },

    GraphViewType.Connectivity: {
        EntityClass.FLIP_FLOP:      NodePolicy(NodeAction.PROMOTE, SuperClass.ATOMIC),
        EntityClass.DSP:            NodePolicy(NodeAction.PROMOTE, SuperClass.ATOMIC),
        EntityClass.BRAM:           NodePolicy(NodeAction.PROMOTE, SuperClass.ATOMIC),
        EntityClass.IO_PORT:        NodePolicy(NodeAction.PROMOTE, SuperClass.ATOMIC),

        EntityClass.RTL_BLOCK:      NodePolicy(NodeAction.MERGE, SuperClass.COMB_CLOUD),
        EntityClass.FSM:            NodePolicy(NodeAction.MERGE, SuperClass.COMB_CLOUD),
        EntityClass.LUT:            NodePolicy(NodeAction.MERGE, SuperClass.COMB_CLOUD),
        EntityClass.MUX:            NodePolicy(NodeAction.MERGE, SuperClass.COMB_CLOUD),

        EntityClass.MODULE_INSTANCE:NodePolicy(NodeAction.ELIMINATE, SuperClass.ELIMINATED),
        EntityClass.PACKAGE_PIN:    NodePolicy(NodeAction.ELIMINATE, SuperClass.ELIMINATED),
        EntityClass.PBLOCK:         NodePolicy(NodeAction.ELIMINATE, SuperClass.ELIMINATED),
        EntityClass.BOARD_CONNECTOR:NodePolicy(NodeAction.ELIMINATE, SuperClass.ELIMINATED),
    },

    GraphViewType.Physical: {
        EntityClass.IO_PORT:        NodePolicy(NodeAction.PROMOTE, SuperClass.ATOMIC),
        EntityClass.PACKAGE_PIN:    NodePolicy(NodeAction.PROMOTE, SuperClass.ATOMIC),
        EntityClass.PBLOCK:         NodePolicy(NodeAction.PROMOTE, SuperClass.ATOMIC),
        EntityClass.BOARD_CONNECTOR:NodePolicy(NodeAction.PROMOTE, SuperClass.ATOMIC),

        EntityClass.DSP:            NodePolicy(NodeAction.MERGE, SuperClass.CONSTRAINT_GROUP),
        EntityClass.BRAM:           NodePolicy(NodeAction.MERGE, SuperClass.CONSTRAINT_GROUP),

        # 나머지는 전부 제거
    },
}


# ============================================================================
# POLICY_MAP_SIMULATION: 동작 검증/테스트벤치용 정책
# ============================================================================
# 목표: 검증 환경과 테스트 대상(DUT)의 관계를 명확히 표현
# 핵심 철학: "테스트에서 무엇을 검증하는가?"
# ============================================================================
POLICY_MAP_SIMULATION: dict[GraphViewType, dict[EntityClass, NodePolicy]] = {

    GraphViewType.Structural: {
        # 시뮬레이션에서는 모듈 계층이 중요 (인터페이스 중심)
        EntityClass.MODULE_INSTANCE: NodePolicy(NodeAction.PROMOTE, SuperClass.ATOMIC),
        EntityClass.IO_PORT:        NodePolicy(NodeAction.PROMOTE, SuperClass.ATOMIC),
        
        # 초기값 설정 블록이나 클럭 생성기는 검증에 필수
        # (파서가 이를 RTL_BLOCK으로 분류할 경우 보존)
        EntityClass.RTL_BLOCK:      NodePolicy(NodeAction.MERGE, SuperClass.MODULE_CLUSTER),
        
        # 내부 로직은 과감하게 합침 (블랙박스 뷰)
        EntityClass.FSM:            NodePolicy(NodeAction.MERGE, SuperClass.MODULE_CLUSTER),
        EntityClass.FLIP_FLOP:      NodePolicy(NodeAction.MERGE, SuperClass.MODULE_CLUSTER),
        EntityClass.LUT:            NodePolicy(NodeAction.MERGE, SuperClass.MODULE_CLUSTER),
        EntityClass.MUX:            NodePolicy(NodeAction.MERGE, SuperClass.MODULE_CLUSTER),
        EntityClass.DSP:            NodePolicy(NodeAction.MERGE, SuperClass.MODULE_CLUSTER),
        EntityClass.BRAM:           NodePolicy(NodeAction.MERGE, SuperClass.MODULE_CLUSTER),

        # 물리적 제약은 시뮬레이션에서 무의미 -> 제거
        EntityClass.PACKAGE_PIN:    NodePolicy(NodeAction.ELIMINATE, SuperClass.ELIMINATED),
        EntityClass.PBLOCK:         NodePolicy(NodeAction.ELIMINATE, SuperClass.ELIMINATED),
        EntityClass.BOARD_CONNECTOR:NodePolicy(NodeAction.ELIMINATE, SuperClass.ELIMINATED),
    },

    GraphViewType.Connectivity: {
        # 모듈 인터페이스는 시뮬레이션의 주요 관심사
        EntityClass.MODULE_INSTANCE: NodePolicy(NodeAction.PROMOTE, SuperClass.ATOMIC),
        EntityClass.IO_PORT:        NodePolicy(NodeAction.PROMOTE, SuperClass.ATOMIC),
        
        # 레지스터는 상태 변화 추적에 유용할 수 있음
        EntityClass.FLIP_FLOP:      NodePolicy(NodeAction.PROMOTE, SuperClass.ATOMIC),
        EntityClass.DSP:            NodePolicy(NodeAction.PROMOTE, SuperClass.ATOMIC),
        EntityClass.BRAM:           NodePolicy(NodeAction.PROMOTE, SuperClass.ATOMIC),
        
        # 내부 로직은 DUT 블랙박스로 표현
        EntityClass.RTL_BLOCK:      NodePolicy(NodeAction.MERGE, SuperClass.MODULE_CLUSTER),
        EntityClass.FSM:            NodePolicy(NodeAction.MERGE, SuperClass.MODULE_CLUSTER),
        EntityClass.LUT:            NodePolicy(NodeAction.MERGE, SuperClass.MODULE_CLUSTER),
        EntityClass.MUX:            NodePolicy(NodeAction.MERGE, SuperClass.MODULE_CLUSTER),

        # 물리적 정보는 제거
        EntityClass.PACKAGE_PIN:    NodePolicy(NodeAction.ELIMINATE, SuperClass.ELIMINATED),
        EntityClass.PBLOCK:         NodePolicy(NodeAction.ELIMINATE, SuperClass.ELIMINATED),
        EntityClass.BOARD_CONNECTOR:NodePolicy(NodeAction.ELIMINATE, SuperClass.ELIMINATED),
    },

    GraphViewType.Physical: {
        # Simulation에서는 Physical View가 의미 없음 (모두 제거)
        # 필요시 향후 확장 가능
    },
}


def select_policy_map(context: GraphContext) -> dict[GraphViewType, dict[EntityClass, NodePolicy]]:
    """
    컨텍스트에 따른 적절한 정책 맵 선택.
    
    Args:
        context: GraphContext 값 (DESIGN 또는 SIMULATION)
        
    Returns:
        선택된 정책 맵
    """
    if context == GraphContext.SIMULATION:
        return POLICY_MAP_SIMULATION
    else:
        # 기본값: DESIGN
        return POLICY_MAP_DESIGN


def get_node_policy(
    node: DKGNode,
    view: GraphViewType,
    context: GraphContext = GraphContext.DESIGN,
) -> NodePolicy:
    """
    노드에 대한 정책 결정.
    
    Args:
        node: 대상 노드
        view: 그래프 뷰 타입
        context: 사용 맥락 (기본값: DESIGN)
        
    Returns:
        적용할 정책 (NodePolicy)
        
    원칙:
    1. 컨텍스트에 따른 정책 맵 선택
    2. 뷰에 해당하는 정책 조회
    3. 엔티티 클래스에 따른 정책 반환
    4. 속성 기반 동적 오버라이딩 (예: testbench 이름 패턴)
    """
    # 1. 컨텍스트에 따른 정책 맵 선택
    policy_map = select_policy_map(context)
    
    # 2. 뷰에 해당하는 정책 조회
    view_policies = policy_map.get(view, {})
    
    # 3. 엔티티 클래스에 따른 기본 정책
    base_policy = view_policies.get(
        node.entity_class,
        NodePolicy(NodeAction.ELIMINATE, SuperClass.ELIMINATED)
    )
    
    # 4. 속성 기반 동적 오버라이딩 (Task 12의 핵심)
    # Design 모드에서: testbench 관련 요소는 강제 제거
    if context == GraphContext.DESIGN:
        is_testbench = (
            node.local_name.lower().startswith("tb_") or
            "testbench" in node.hier_path.lower() or
            "sim" in node.hier_path.lower()
        )
        if is_testbench:
            return NodePolicy(NodeAction.ELIMINATE, SuperClass.ELIMINATED)
    
    # Simulation 모드에서: 시뮬레이션 스큨러러스 생성기는 보존
    if context == GraphContext.SIMULATION:
        is_important_for_sim = (
            node.local_name.lower().startswith("clk_gen") or
            node.local_name.lower().startswith("reset_gen") or
            "initial" in node.attributes.get("verilog_construct", "").lower()
        )
        if is_important_for_sim and base_policy.action == NodeAction.MERGE:
            # 클럭/리셋 생성기는 Atomic으로 상향
            return NodePolicy(NodeAction.PROMOTE, SuperClass.ATOMIC)
    
    return base_policy


class ViewBuilder:
    def __init__(
        self,
        nodes: Dict[str, DKGNode],
        edges: Dict[str, DKGEdge],
        view: GraphViewType,
        context: GraphContext = GraphContext.DESIGN,
    ):
        self.nodes = nodes
        self.edges = edges
        self.view = view
        self.context = context

        self.node_to_super: Dict[str, str] = {}
        self.super_nodes: Dict[str, SuperNode] = {}
        self.super_edges: Dict[Tuple[str, str], SuperEdge] = {}

    def _neighbors_1hop(self, nid: str) -> Set[str]:
        n = self.nodes[nid]
        nbrs = set()
        for eid in n.in_edges + n.out_edges:
            e = self.edges[eid]
            nbrs.add(e.src_node)
            nbrs.add(e.dst_node)
        return nbrs

    def cycle1_promote(self) -> None:
        for n in self.nodes.values():
            node_policy = get_node_policy(n, self.view, self.context)
            if node_policy.action != NodeAction.PROMOTE:
                continue
            if node_policy.super_class is None:
                continue

            sn = SuperNode(
                node_id=f"SN_{n.node_id}",
                super_class=node_policy.super_class,
                member_nodes={n.node_id},
                member_edges=set(),
                provenances=list(n.provenances),
            )
            sn.canonical_name = make_supernode_canonical_name(sn, self.nodes)
            sn.display_name = make_supernode_display_name(sn)
            self.super_nodes[sn.node_id] = sn
            self.node_to_super[n.node_id] = sn.node_id

    def cycle2_merge(self) -> None:
        # 각 노드가 머지될 super_class 결정
        node_merge_class: Dict[str, SuperClass] = {}
        for nid, n in self.nodes.items():
            node_policy = get_node_policy(n, self.view, self.context)
            if node_policy.action == NodeAction.MERGE and node_policy.super_class is not None:
                node_merge_class[nid] = node_policy.super_class
        
        merge_candidates = set(node_merge_class.keys())
        visited: Set[str] = set()

        for nid in merge_candidates:
            if nid in visited:
                continue

            target_class = node_merge_class[nid]
            stack = [nid]
            component: Set[str] = set()

            while stack:
                cur = stack.pop()
                if cur in visited or cur not in merge_candidates:
                    continue
                # 같은 super_class를 가진 노드만 처리
                if node_merge_class[cur] != target_class:
                    continue

                visited.add(cur)
                component.add(cur)

                for nb in self._neighbors_1hop(cur):
                    if nb in merge_candidates and node_merge_class.get(nb) == target_class:
                        stack.append(nb)

            if not component:
                continue

            sn_id = make_supernode_id(
                view=self.view,
                super_class=target_class,
                member_node_ids=component,
                policy_version="v2",
            )

            sn = SuperNode(
                node_id=sn_id,
                super_class=target_class,
                member_nodes=component,
                member_edges=set(),
            )
            sn.canonical_name = make_supernode_canonical_name(sn, self.nodes)
            sn.display_name = make_supernode_display_name(sn)

            self.super_nodes[sn.node_id] = sn
            for n in component:
                self.node_to_super[n] = sn.node_id

    def cycle2_5_eliminate(self) -> None:
        for nid, n in self.nodes.items():
            if nid in self.node_to_super:
                continue

            node_policy = get_node_policy(n, self.view, self.context)
            if node_policy.action != NodeAction.ELIMINATE:
                raise RuntimeError(f"Unassigned node in view {self.view}: {nid}")

            eliminate_class = node_policy.super_class if node_policy.super_class is not None else SuperClass.ELIMINATED

            sn = SuperNode(
                node_id=make_supernode_id(
                    view=self.view,
                    super_class=eliminate_class,
                    member_node_ids={nid},
                    policy_version="v1",
                ),
                super_class=eliminate_class,
                member_nodes={nid},
                member_edges=set(),
            )
            sn.canonical_name = make_supernode_canonical_name(sn, self.nodes)
            sn.display_name = make_supernode_display_name(sn)

            self.super_nodes[sn.node_id] = sn
            self.node_to_super[nid] = sn.node_id

    def cycle3_rewrite_edges(self) -> None:
        for e in self.edges.values():
            src_sn = self.node_to_super[e.src_node]
            dst_sn = self.node_to_super[e.dst_node]

            if src_sn == dst_sn:
                self.super_nodes[src_sn].member_edges.add(e.edge_id)
                continue

            key = (src_sn, dst_sn)
            if key not in self.super_edges:
                self.super_edges[key] = SuperEdge(
                    edge_id=make_superedge_id(src_sn, dst_sn, set()),
                    src_node=src_sn,
                    dst_node=dst_sn,
                    member_edges=set(),
                    member_nodes=set(),
                    relation_types=set(),
                    flow_types=set(),
                    provenances=[],
                )
                self.super_edges[key].canonical_name = make_superedge_canonical_name(
                    self.super_edges[key],
                    self.super_nodes,
                )
                self.super_edges[key].display_name = make_superedge_display_name(
                    self.super_edges[key],
                )

            se = self.super_edges[key]
            se.member_edges.add(e.edge_id)
            se.member_nodes.update({e.src_node, e.dst_node})
            se.relation_types.add(e.relation_type)
            se.flow_types.add(e.flow_type)
            se.provenances.extend(e.provenances)

    def build(self) -> SuperGraph:
        self.cycle1_promote()
        self.cycle2_merge()
        self.cycle2_5_eliminate()
        self.cycle3_rewrite_edges()

        return SuperGraph(
            super_nodes=self.super_nodes,
            super_edges=self.super_edges,
            node_to_super=self.node_to_super,
        )


# ============================================================================
# Analysis Attachment Helper Functions
# ============================================================================
# Analysis는 구조 로직에서 직접 참조하지 않으며, 결과의 귀속 대상으로만 사용됩니다.
# ============================================================================

def attach_timing_analysis_to_supernode(
    sn: SuperNode,
    metrics: TimingNodeMetrics
) -> None:
    """
    SuperNode에 Timing Analysis 결과를 부착합니다.
    
    원칙:
    - 구조 변경 없음
    - 기존 analysis["timing"]은 전체 교체됨 (immutable snapshot)
    - 구조 로직은 이 함수를 호출하지 않음
    """
    sn.analysis[AnalysisKind.TIMING] = metrics


def attach_timing_analysis_to_superedge(
    se: SuperEdge,
    metrics: TimingEdgeMetrics
) -> None:
    """
    SuperEdge에 Timing Analysis 결과를 부착합니다.
    
    원칙:
    - 구조 변경 없음
    - 기존 analysis["timing"]은 전체 교체됨 (immutable snapshot)
    - 구조 로직은 이 함수를 호출하지 않음
    """
    se.analysis[AnalysisKind.TIMING] = metrics


def get_timing_analysis_from_supernode(
    sn: SuperNode
) -> Optional[TimingNodeMetrics]:
    """
    SuperNode에서 Timing Analysis 결과를 조회합니다.
    
    Returns:
        TimingNodeMetrics or None if not attached
    """
    return sn.analysis.get(AnalysisKind.TIMING)


def get_timing_analysis_from_superedge(
    se: SuperEdge
) -> Optional[TimingEdgeMetrics]:
    """
    SuperEdge에서 Timing Analysis 결과를 조회합니다.
    
    Returns:
        TimingEdgeMetrics or None if not attached
    """
    return se.analysis.get(AnalysisKind.TIMING)
