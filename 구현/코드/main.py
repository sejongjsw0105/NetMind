#region Parser
from dataclasses import dataclass
#region Common Classes
@dataclass
class Provenance:
    origin_file: Optional[str] = None
    origin_line: Optional[int] = None
    tool_stage: str = "rtl"          # rtl / synth / timing / constraint
    confidence: str = "exact"        # exact / inferred
def add_provenance(obj, prov: Provenance, make_primary=False):
    obj.provenances.append(prov)

    if make_primary or obj.primary_provenance is None:
        obj.primary_provenance = prov
def merge_provenances_nodes(nodes):
    new_provs = []
    for n in nodes:
        new_provs.extend(n.provenances)

    # 대표 provenance 계산
    files = [p.origin_file for p in new_provs if p.origin_file]
    lines = [p.origin_line for p in new_provs if p.origin_line]

    primary = Provenance(
        origin_file=files[0] if files else None,
        origin_line=min(lines) if lines else None,
        tool_stage="rtl",
        confidence="inferred"
    )

    return primary, new_provs
def merge_provenances_edges(edges):
    new_provs = []
    for e in edges:
        new_provs.extend(e.provenances)

    # 대표 provenance 계산
    files = [p.origin_file for p in new_provs if p.origin_file]
    lines = [p.origin_line for p in new_provs if p.origin_line]

    primary = Provenance(
        origin_file=files[0] if files else None,
        origin_line=min(lines) if lines else None,
        tool_stage="rtl",
        confidence="inferred"
    )

    return primary, new_provs

#endregion
#region Yosys HDL Parser for WSL
import subprocess
import glob
import os
from pathlib import Path

# ================== 설정 ==================
SRC_DIR_WIN = r"C:\Users\User\NetMind\구현\예시"   # Windows 경로
OUT_JSON_WIN = r"C:\Users\User\NetMind\구현\design.json"
TOP_MODULE = "riscvsingle"
# ==========================================

def win_to_wsl_path(win_path):
    """Windows → WSL 경로 변환 (정확 버전)"""
    p = Path(win_path).resolve()
    drive = p.drive[0].lower()  # 'C:' → 'c'
    path_no_drive = p.as_posix()[2:]  # 'C:/Users/...' → '/Users/...'
    return f"/mnt/{drive}{path_no_drive}"


# 1️⃣ HDL 파일 수집 (Windows 기준)
verilog_files = glob.glob(os.path.join(SRC_DIR_WIN, "*.v"))
sv_files = glob.glob(os.path.join(SRC_DIR_WIN, "*.sv"))
all_files_win = verilog_files + sv_files

if not all_files_win:
    raise RuntimeError("No HDL files found.")

# 2️⃣ 경로를 WSL 형식으로 변환
all_files_wsl = [win_to_wsl_path(f) for f in all_files_win]
out_json_wsl = win_to_wsl_path(OUT_JSON_WIN)

# 3️⃣ Yosys 명령 문자열 구성
yosys_script = f"""
read_verilog -sv {' '.join(all_files_wsl)};
hierarchy -check -top {TOP_MODULE};
proc;
opt;
write_json {out_json_wsl}
"""

# 4️⃣ WSL 통해 Yosys 실행
subprocess.run(
    ["wsl", "yosys", "-p", yosys_script],
    check=True
)

print("Yosys parsing complete.")
#endregion
#region Get JSON File
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Tuple
import json
@dataclass
class Wire:
    wire_id: int
    name: str | None = None
    drivers: list[str] = field(default_factory=list)
    loads: list[str] = field(default_factory=list)
    src: Optional[str] = None

@dataclass
class CellIR:
    name: str
    type: str
    module: str
    port_dirs: dict[str, str]
    connections: dict[str, list[int]]
    src: Optional[str] = None

with open(OUT_JSON_WIN) as f:  # :contentReference[oaicite:1]{index=0}
    yosys = json.load(f)
wires: dict[int, Wire] = {}

def get_wire(wid):
    if isinstance(wid, str):  # "x" or constant
        return None
    if wid not in wires:
        wires[wid] = Wire(wid)
    return wires[wid]

for mod_name, mod in yosys["modules"].items():
    for netname, netinfo in mod.get("netnames", {}).items():
        src = netinfo.get("src")
        for wid in netinfo["bits"]:
            w = get_wire(wid)
            if w:
                w.name = netname
                w.src = src
cells: list[CellIR] = []

for mod_name, mod in yosys["modules"].items():
    for cname, c in mod.get("cells", {}).items():
        cells.append(CellIR(
            name=cname,
            type=c["type"],
            module=mod_name,
            port_dirs=c["port_directions"],
            connections=c["connections"],
            src=c.get("src")
        ))
for cell in cells:
    node_id = f"{cell.module}.{cell.name}"

    for port, bits in cell.connections.items():
        direction = cell.port_dirs[port]

        for wid in bits:
            w = get_wire(wid)
            if not w:
                continue

            if direction == "output":
                w.drivers.append(node_id)
            else:
                w.loads.append(node_id)
def parse_src(src_str):
    if not src_str:
        return None, None
    try:
        file_part, line_part = src_str.split(":")
        line = int(line_part.split(".")[0])
        return file_part, line
    except:
        return None, None
#endregion
#endregion
#region Classes
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Tuple

#region Node/Entity Classes
class EntityClass(str, Enum):
    # Logical
    MODULE_INSTANCE = "ModuleInstance"
    RTL_BLOCK = "RTLBlock"
    FSM = "FSM"

    # Structural primitives
    FLIP_FLOP = "FlipFlop"
    LUT = "LUT"
    MUX = "MUX"
    DSP = "DSP"
    BRAM = "BRAM"

    # Physical
    IO_PORT = "IOPort"
    PACKAGE_PIN = "PackagePin"
    PBLOCK = "Pblock"
    BOARD_CONNECTOR = "BoardConnector"

@dataclass
class DKGNode:
    node_id: str                     # canonical unique ID
    entity_class: EntityClass

    hier_path: str                   # top.u1.u2
    local_name: str                  # e.g., u_core

    # ---- Display / AI ----
    display_name: Optional[str] = None
    short_alias: Optional[str] = None

    # ---- Structural ----
    parameters: Dict[str, str] = field(default_factory=dict)
    attributes: Dict[str, str] = field(default_factory=dict)

    # ---- Timing ----
    clock_domain: Optional[str] = None
    arrival_time: Optional[float] = None
    required_time: Optional[float] = None
    slack: Optional[float] = None

    # ---- Graph connectivity (filled by graph engine) ----
    in_edges: List[str] = field(default_factory=list)
    out_edges: List[str] = field(default_factory=list)

    #---- Provenance ----
    provenances: List[Provenance] = field(default_factory=list)
    primary_provenance: Optional[Provenance] = None

#endregion
#region Edge/Relation Classes
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
class DKGEdge:
    edge_id: str
    src_node: str
    dst_node: str

    relation_type: RelationType
    flow_type: EdgeFlowType

    # ---- Signal info ----
    signal_name: str
    canonical_name: str              # top.u1.data[3]
    bit_range: Optional[Tuple[int, int]] = None  # (msb, lsb)
    net_id: Optional[str] = None

    # ---- Driver / Load ----
    driver_type: Optional[str] = None  # reg/wire/ff/lut/port
    fanout_count: Optional[int] = None

    # ---- Clock / Reset ----
    clock_signal: Optional[str] = None
    reset_signal: Optional[str] = None
    clock_domain_id: Optional[str] = None

    # ---- Constraints ----
    timing_exception: Optional[str] = None  # false_path, multicycle
    parameters: Dict[str, Any] = field(default_factory=dict)

    # ---- Timing ----
    delay: Optional[float] = None
    arrival_time: Optional[float] = None
    required_time: Optional[float] = None
    slack: Optional[float] = None

    # ---- Misc ----
    attributes: Dict[str, Any] = field(default_factory=dict)

    #---- Provenance ----
    provenances: List[Provenance] = field(default_factory=list)
    primary_provenance: Optional[Provenance] = None
import re
from collections import defaultdict

def split_signal_bit(sig):
    """
    data[3] → ("data", 3)
    data → ("data", None)
    """
    m = re.match(r"(.+)\[(\d+)\]$", sig)
    if m:
        return m.group(1), int(m.group(2))
    return sig, None


def merge_bit_edges_to_bus(edges: dict[str, DKGEdge]) -> dict[str, DKGEdge]:
    groups = defaultdict(list)

    # 1️⃣ 병합 가능한 후보 그룹화
    for e in edges.values():
        base, bit = split_signal_bit(e.signal_name)

        key = (
            e.src_node,
            e.dst_node,
            e.relation_type,
            e.flow_type,
            base
        )

        groups[key].append((bit, e))

    new_edges = {}
    new_eid = 0

    # 2️⃣ 각 그룹에서 연속 비트 병합
    for key, items in groups.items():
        src, dst, rel, flow, base = key

        # bit 없는 신호는 그대로 유지
        if all(bit is None for bit, _ in items):
            for _, e in items:
                new_edges[e.edge_id] = e
            continue

        # 비트 기준 정렬
        items.sort(key=lambda x: (-1 if x[0] is None else x[0]))

        current_bucket = []
        prev_bit = None

        def flush_bucket(bucket):
            nonlocal new_eid
            if not bucket:
                return

            bits = [b for b, _ in bucket if b is not None]
            edges_in_bucket = [e for _, e in bucket]

            if len(bits) <= 1:
                # 병합할 필요 없음
                e = edges_in_bucket[0]
                new_edges[e.edge_id] = e
                return

            msb = max(bits)
            lsb = min(bits)

            # 대표 edge 생성 (첫 edge 복사 기반)
            base_edge = edges_in_bucket[0]
            merged = DKGEdge(
                edge_id=f"bus_e{new_eid}",
                src_node=base_edge.src_node,
                dst_node=base_edge.dst_node,
                relation_type=base_edge.relation_type,
                flow_type=base_edge.flow_type,
                signal_name=f"{base}[{msb}:{lsb}]",
                canonical_name=base_edge.canonical_name,
                bit_range=(msb, lsb),
                net_id=base_edge.net_id,
                driver_type=base_edge.driver_type,
                fanout_count=base_edge.fanout_count,
                clock_signal=base_edge.clock_signal,
                reset_signal=base_edge.reset_signal,
                clock_domain_id=base_edge.clock_domain_id,
                timing_exception=base_edge.timing_exception,
                delay=base_edge.delay,
                arrival_time=base_edge.arrival_time,
                required_time=base_edge.required_time,
                slack=base_edge.slack,
                attributes=dict(base_edge.attributes),
                provenances=[],
                primary_provenance=None
            )

            # provenance 병합
            primary, provs = merge_provenances_edges(edges_in_bucket)
            merged.provenances = provs
            merged.primary_provenance = primary

            # 어떤 bit들이 합쳐졌는지 기록
            merged.attributes["merged_bits"] = sorted(bits)

            new_edges[merged.edge_id] = merged
            new_eid += 1

        for bit, e in items:
            if bit is None:
                flush_bucket(current_bucket)
                current_bucket = []
                new_edges[e.edge_id] = e
                prev_bit = None
                continue

            if prev_bit is None or bit == prev_bit - 1:
                current_bucket.append((bit, e))
            else:
                flush_bucket(current_bucket)
                current_bucket = [(bit, e)]

            prev_bit = bit

        flush_bucket(current_bucket)

    return new_edges

#endregion
#endregion
#region Build DKG
def map_cell_type(t: str) -> EntityClass:
    if t in ["$adff", "$dff"]:
        return EntityClass.FLIP_FLOP
    if t in ["$mux", "$pmux"]:
        return EntityClass.MUX
    if t in ["$add", "$sub", "$and", "$or"]:
        return EntityClass.RTL_BLOCK
    return EntityClass.RTL_BLOCK
nodes: dict[str, DKGNode] = {}

for cell in cells:
    nid = f"{cell.module}.{cell.name}"

    nodes[nid] = DKGNode(
        node_id=nid,
        entity_class=map_cell_type(cell.type),
        hier_path=cell.module,
        local_name=cell.name,
    )
    file, line = parse_src(cell.src)
    prov = Provenance(
        origin_file=file,
        origin_line=line,
        tool_stage="rtl",
        confidence="exact"
    )
    add_provenance(nodes[nid] , prov, make_primary=True)
edges: dict[str, DKGEdge] = {}
eid = 0

for w in wires.values():
    for src in w.drivers:
        for dst in w.loads:
            edge_id = f"e{eid}"
            eid += 1

            edges[edge_id] = DKGEdge(
                edge_id=edge_id,
                src_node=src,
                dst_node=dst,
                relation_type=RelationType.DATA,
                flow_type=EdgeFlowType.COMBINATIONAL,
                signal_name=w.name or f"wire_{w.wire_id}",
                canonical_name=f"{src}->{dst}",
            )
            
            file, line = parse_src(w.src)

            prov = Provenance(
                origin_file=file,
                origin_line=line,
                tool_stage="rtl",
                confidence="exact"
            )

            add_provenance(edges[edge_id] , prov, make_primary=True)
            nodes[src].out_edges.append(edge_id)
            nodes[dst].in_edges.append(edge_id)
edges = merge_bit_edges_to_bus(edges)
#endregion
#region Output Summary (Temporary)
print("===== GRAPH SUMMARY =====")
print(f"Total wires   : {len(wires)}")
print(f"Total cells   : {len(cells)}")
print(f"Total nodes   : {len(nodes)}")
print(f"Total edges   : {len(edges)}")
print("=========================")
import random

sample = random.choice(list(nodes.values()))

print("\n===== SAMPLE NODE =====")
print("Node:", sample.node_id, sample.entity_class)
print("IN edges:", len(sample.in_edges))
print("OUT edges:", len(sample.out_edges))

for eid in sample.out_edges[:5]:
    e = edges[eid]
    print("  →", e.signal_name, "→", e.dst_node)
print("=========================")
fanouts = [len(w.loads) for w in wires.values() if w.loads]
print("\nMax fanout:", max(fanouts))
print("Avg fanout:", sum(fanouts)/len(fanouts))
print("=========================")
target = "clk"

print("\n===== TRACE SIGNAL:", target, "=====")
for w in wires.values():
    if w.name == target:
        print("Drivers:", w.drivers)
        print("Loads  :", w.loads)
print("=========================")
import networkx as nx
import matplotlib.pyplot as plt

G = nx.DiGraph()

for nid in nodes:
    G.add_node(nid)

for e in edges.values():
    G.add_edge(e.src_node, e.dst_node, label=e.signal_name)

sub_nodes = list(nodes.keys())[:30]
def clean_label(name):
    return name.replace("\\", "").replace("$", "")

H = G.subgraph(sub_nodes)
labels = {n: clean_label(n) for n in H.nodes()}

nx.draw(H, labels=labels, with_labels=True, node_size=500, font_size=6)
plt.show()

#endregion
#region Make SubGraph

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Set, Tuple, Any, List

#region View / Action Definitions
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

#endregion

#region SuperGraph IR
@dataclass
class SuperNode:
    node_id: str
    super_class: SuperClass
    member_nodes: Set[str]
    member_edges: Set[str]
    aggregated_attrs: Dict[str, Any] = field(default_factory=dict)
    provenances: List[Provenance] = field(default_factory=list)


@dataclass
class SuperEdge:
    edge_id: str
    src_node: str          # SuperNode ID
    dst_node: str          # SuperNode ID
    member_edges: Set[str]
    member_nodes: Set[str]
    relation_types: Set[RelationType]
    flow_types: Set[EdgeFlowType]
    provenances: List[Provenance] = field(default_factory=list)


@dataclass
class SuperGraph:
    super_nodes: Dict[str, SuperNode]
    super_edges: Dict[Tuple[str, str], SuperEdge]
    node_to_super: Dict[str, str]


#endregion
#region View Policy

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


#endregion
#region View Builder

class ViewBuilder:
    def __init__(self, nodes: Dict[str, DKGNode], edges: Dict[str, DKGEdge], view: GraphViewType):
        self.nodes = nodes
        self.edges = edges
        self.view = view

        self.node_to_super: Dict[str, str] = {}
        self.super_nodes: Dict[str, SuperNode] = {}
        self.super_edges: Dict[Tuple[str, str], SuperEdge] = {}

    # -------- helpers --------

    def _neighbors_1hop(self, nid: str) -> Set[str]:
        n = self.nodes[nid]
        nbrs = set()
        for eid in n.in_edges + n.out_edges:
            e = self.edges[eid]
            nbrs.add(e.src_node)
            nbrs.add(e.dst_node)
        return nbrs

    # -------- cycle 1 --------

    def cycle1_promote(self):
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
            self.super_nodes[sn.node_id] = sn
            self.node_to_super[n.node_id] = sn.node_id

    # -------- cycle 2 --------

    def cycle2_merge(self):
        merge_candidates = {
            nid for nid, n in self.nodes.items()
            if VIEW_POLICY[self.view].get(n.entity_class) == NodeAction.MERGE
        }

        visited = set()

        for nid in merge_candidates:
            if nid in visited:
                continue

            stack = [nid]
            component = set()

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

            sn = SuperNode(
                node_id=f"SN_MERGE_{len(self.super_nodes)}",
                super_class=SuperClass.COMB_CLOUD,
                member_nodes=component,
                member_edges=set(),
            )

            self.super_nodes[sn.node_id] = sn
            for n in component:
                self.node_to_super[n] = sn.node_id

    # -------- cycle 2.5 --------

    def cycle2_5_eliminate(self):
        for nid, n in self.nodes.items():
            if nid in self.node_to_super:
                continue

            if VIEW_POLICY[self.view].get(n.entity_class) != NodeAction.ELIMINATE:
                raise RuntimeError(f"Unassigned node in view {self.view}: {nid}")

            sn = SuperNode(
                node_id=f"SN_ELIM_{nid}",
                super_class=SuperClass.ELIMINATED,
                member_nodes={nid},
                member_edges=set(),
            )

            self.super_nodes[sn.node_id] = sn
            self.node_to_super[nid] = sn.node_id

    # -------- cycle 3 --------

    def cycle3_rewrite_edges(self):
        for e in self.edges.values():
            src_sn = self.node_to_super[e.src_node]
            dst_sn = self.node_to_super[e.dst_node]

            if src_sn == dst_sn:
                self.super_nodes[src_sn].member_edges.add(e.edge_id)
                continue

            key = (src_sn, dst_sn)
            if key not in self.super_edges:
                self.super_edges[key] = SuperEdge(
                    edge_id=f"SE_{src_sn}_to_{dst_sn}",
                    src_node=src_sn,
                    dst_node=dst_sn,
                    member_edges=set(),
                    member_nodes=set(),
                    relation_types=set(),
                    flow_types=set(),
                    provenances=[],
                )

            se = self.super_edges[key]
            se.member_edges.add(e.edge_id)
            se.member_nodes.update({e.src_node, e.dst_node})
            se.relation_types.add(e.relation_type)
            se.flow_types.add(e.flow_type)
            se.provenances.extend(e.provenances)

    # -------- entry --------

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
#endregion
#endregion
