from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .provenance import Provenance


class EntityClass(str, Enum):
    MODULE_INSTANCE = "ModuleInstance"
    RTL_BLOCK = "RTLBlock"
    FSM = "FSM"

    FLIP_FLOP = "FlipFlop"
    LUT = "LUT"
    MUX = "MUX"
    DSP = "DSP"
    BRAM = "BRAM"

    IO_PORT = "IOPort"
    PACKAGE_PIN = "PackagePin"
    PBLOCK = "Pblock"
    BOARD_CONNECTOR = "BoardConnector"


class RelationType(str, Enum):
    DATA = "DataRelation"
    CLOCK = "ClockRelation"
    RESET = "ResetRelation"
    PARAMETER = "ParameterRelation"
    CONSTRAINT = "ConstraintRelation"
    PHYSICAL_MAP = "PhysicalMappingRelation"


class EdgeFlowType(str, Enum):
    COMBINATIONAL = "combinational"
    SEQ_LAUNCH = "sequential_launch"
    SEQ_CAPTURE = "sequential_capture"
    CLOCK_TREE = "clock_tree"
    ASYNC_RESET = "async_reset"


@dataclass
class DKGNode:
    node_id: str
    entity_class: EntityClass
    hier_path: str
    local_name: str
    canonical_name: Optional[str] = None

    display_name: Optional[str] = None
    short_alias: Optional[str] = None

    parameters: Dict[str, str] = field(default_factory=dict)
    attributes: Dict[str, str] = field(default_factory=dict)

    clock_domain: Optional[str] = None
    arrival_time: Optional[float] = None
    required_time: Optional[float] = None
    slack: Optional[float] = None

    in_edges: List[str] = field(default_factory=list)
    out_edges: List[str] = field(default_factory=list)

    provenances: List[Provenance] = field(default_factory=list)
    primary_provenance: Optional[Provenance] = None


@dataclass
class DKGEdge:
    edge_id: str
    src_node: str
    dst_node: str

    relation_type: RelationType
    flow_type: EdgeFlowType

    signal_name: str
    canonical_name: str
    bit_range: Optional[Tuple[int, int]] = None
    net_id: Optional[str] = None

    driver_type: Optional[str] = None
    fanout_count: Optional[int] = None

    clock_signal: Optional[str] = None
    reset_signal: Optional[str] = None
    clock_domain_id: Optional[str] = None

    timing_exception: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)

    delay: Optional[float] = None
    arrival_time: Optional[float] = None
    required_time: Optional[float] = None
    slack: Optional[float] = None

    attributes: Dict[str, Any] = field(default_factory=dict)

    provenances: List[Provenance] = field(default_factory=list)
    primary_provenance: Optional[Provenance] = None


def make_node_canonical_name(node: DKGNode) -> str:
    base = node.hier_path

    cls = node.entity_class
    if cls == EntityClass.FLIP_FLOP:
        suffix = f"reg_{node.local_name}"
    elif cls == EntityClass.MUX:
        suffix = "mux"
    elif cls == EntityClass.LUT:
        suffix = "comb"
    elif cls == EntityClass.BRAM:
        suffix = "bram"
    elif cls == EntityClass.DSP:
        suffix = "dsp"
    elif cls == EntityClass.IO_PORT:
        suffix = f"port_{node.local_name}"
    else:
        suffix = node.local_name or cls.value.lower()

    return f"{base}.{suffix}"


def make_node_display_name(node: DKGNode) -> str:
    if node.entity_class == EntityClass.FLIP_FLOP:
        return f"Reg {node.local_name}"
    if node.entity_class == EntityClass.BRAM:
        return "BRAM"
    if node.entity_class == EntityClass.MUX:
        return "MUX"
    if node.entity_class == EntityClass.LUT:
        return "Logic"
    if node.entity_class == EntityClass.DSP:
        return "DSP"
    if node.entity_class == EntityClass.IO_PORT:
        return f"Port {node.local_name}"

    return node.local_name or node.entity_class.value


def make_edge_canonical_name(e: DKGEdge, nodes: dict[str, DKGNode]) -> str:
    src = nodes[e.src_node].canonical_name
    dst = nodes[e.dst_node].canonical_name

    if e.bit_range:
        msb, lsb = e.bit_range
        sig = f"{e.signal_name}[{msb}:{lsb}]"
    else:
        sig = e.signal_name

    return f"{src} -> {dst} : {sig}"


def make_edge_display_name(e: DKGEdge) -> str:
    if e.bit_range:
        msb, lsb = e.bit_range
        return f"{e.signal_name}[{msb}:{lsb}]"
    return e.signal_name
