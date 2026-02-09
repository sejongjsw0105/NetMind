from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from .graph import DKGEdge, DKGNode, EdgeFlowType, EntityClass, RelationType
from .provenance import Provenance
from .utils import stable_hash


class GraphViewType(str, Enum):
    Structural = "Structural"
    Timing = "Timing"
    Connectivity = "Connectivity"
    Physical = "Physical"


class SuperClass(str, Enum):
    ATOMIC = "Atomic"
    MODULE_CLUSTER = "ModuleCluster"
    SEQ_CHAIN = "SequentialChain"
    COMB_CLOUD = "CombinationalCloud"
    IO_CLUSTER = "IOCluster"
    CONSTRAINT_GROUP = "ConstraintGroup"
    CRITICAL_REGION = "CriticalRegion"
    SLACK_REGION = "SlackRegion"
    ELIMINATED = "EliminatedNode"


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


VIEW_POLICY: Dict[GraphViewType, Dict[EntityClass, NodeAction]] = {
    GraphViewType.Structural: {
        EntityClass.MODULE_INSTANCE: NodeAction.PROMOTE,
        EntityClass.FLIP_FLOP: NodeAction.MERGE,
        EntityClass.LUT: NodeAction.MERGE,
        EntityClass.MUX: NodeAction.MERGE,
        EntityClass.DSP: NodeAction.MERGE,
        EntityClass.BRAM: NodeAction.MERGE,
        EntityClass.IO_PORT: NodeAction.PROMOTE,
        EntityClass.PACKAGE_PIN: NodeAction.ELIMINATE,
        EntityClass.PBLOCK: NodeAction.ELIMINATE,
    },
    GraphViewType.Connectivity: {
        EntityClass.FLIP_FLOP: NodeAction.PROMOTE,
        EntityClass.DSP: NodeAction.PROMOTE,
        EntityClass.BRAM: NodeAction.PROMOTE,
        EntityClass.LUT: NodeAction.MERGE,
        EntityClass.MUX: NodeAction.MERGE,
        EntityClass.MODULE_INSTANCE: NodeAction.ELIMINATE,
    },
}


class ViewBuilder:
    def __init__(self, nodes: Dict[str, DKGNode], edges: Dict[str, DKGEdge], view: GraphViewType):
        self.nodes = nodes
        self.edges = edges
        self.view = view

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
            if VIEW_POLICY[self.view].get(n.entity_class) != NodeAction.PROMOTE:
                continue

            sn = SuperNode(
                node_id=f"SN_{n.node_id}",
                super_class=SuperClass.ATOMIC,
                member_nodes={n.node_id},
                member_edges=set(),
                provenances=list(n.provenances),
            )
            sn.canonical_name = make_supernode_canonical_name(sn, self.nodes)
            sn.display_name = make_supernode_display_name(sn)
            self.super_nodes[sn.node_id] = sn
            self.node_to_super[n.node_id] = sn.node_id

    def cycle2_merge(self) -> None:
        merge_candidates = {
            nid
            for nid, n in self.nodes.items()
            if VIEW_POLICY[self.view].get(n.entity_class) == NodeAction.MERGE
        }

        visited: Set[str] = set()

        for nid in merge_candidates:
            if nid in visited:
                continue

            stack = [nid]
            component: Set[str] = set()

            while stack:
                cur = stack.pop()
                if cur in visited or cur not in merge_candidates:
                    continue

                visited.add(cur)
                component.add(cur)

                for nb in self._neighbors_1hop(cur):
                    stack.append(nb)

            if not component:
                continue

            sn_id = make_supernode_id(
                view=self.view,
                super_class=SuperClass.COMB_CLOUD,
                member_node_ids=component,
                policy_version="v1",
            )

            sn = SuperNode(
                node_id=sn_id,
                super_class=SuperClass.COMB_CLOUD,
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

            if VIEW_POLICY[self.view].get(n.entity_class) != NodeAction.ELIMINATE:
                raise RuntimeError(f"Unassigned node in view {self.view}: {nid}")

            sn = SuperNode(
                node_id=make_supernode_id(
                    view=self.view,
                    super_class=SuperClass.ELIMINATED,
                    member_node_ids={nid},
                    policy_version="v1",
                ),
                super_class=SuperClass.ELIMINATED,
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
