#region Parser
# .rpt/.xdc/.bd/.tcl 파서는 직접 추가 예정 
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
def is_clock_name(name: str) -> bool:
    n = name.lower()
    return (
        n == "clk" or
        n.startswith("clk") or
        n.endswith("_clk") or
        "clock" in n
    )
def is_reset_name(name: str) -> bool:
    n = name.lower()
    return (
        n == "rst" or
        n.startswith("rst") or
        n.startswith("reset")
    )
def is_active_low(name: str) -> bool:
    return name.lower().endswith("_n")
def is_ff_cell(cell_type: str) -> bool:
    return cell_type in {
        "$dff", "$adff", "$sdff",
        "$dffe", "$sdffe"
    }
def is_async_reset_ff(cell_type: str) -> bool:
    return cell_type == "$adff"
def is_sync_reset_ff(cell_type: str) -> bool:
    return cell_type == "$sdff"
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

    return f"{src} → {dst} : {sig}"
def make_edge_display_name(e: DKGEdge) -> str:
    if e.bit_range:
        msb, lsb = e.bit_range
        return f"{e.signal_name}[{msb}:{lsb}]"
    return e.signal_name
def make_supernode_canonical_name(
    sn: SuperNode,
    nodes: dict[str, DKGNode]
) -> str:
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
def make_superedge_canonical_name(
    se: SuperEdge,
    super_nodes: dict[str, SuperNode]
) -> str:
    src = super_nodes[se.src_node].canonical_name
    dst = super_nodes[se.dst_node].canonical_name
    return f"{src} → {dst}"
def make_superedge_display_name(se: SuperEdge) -> str:
    if len(se.relation_types) == 1:
        return next(iter(se.relation_types)).value.replace("Relation", "")
    return "Multiple Signals"


@dataclass
class DKGNode:
    node_id: str                 # Internal ID
    entity_class: EntityClass
    hier_path: str                   # top.u1.u2
    local_name: str                  # e.g., u_core
    canonical_name: Optional[str] = None
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
def detect_clock_reset_signals(
    nodes: Dict[str, DKGNode],
    edges: Dict[str, DKGEdge],
):
    clock_nets = set()
    reset_nets = set()

    # 1️⃣ net name 기반
    for e in edges.values():
        if is_clock_name(e.signal_name):
            clock_nets.add(e.signal_name)
        if is_reset_name(e.signal_name):
            reset_nets.add(e.signal_name)

    # 2️⃣ FF cell 기반 보강
    for n in nodes.values():
        if n.entity_class != EntityClass.FLIP_FLOP:
            continue

        for eid in n.in_edges:
            e = edges[eid]

            if is_clock_name(e.signal_name):
                clock_nets.add(e.signal_name)

            if is_reset_name(e.signal_name):
                reset_nets.add(e.signal_name)

    return clock_nets, reset_nets
def assign_edge_flow_types(
    nodes: Dict[str, DKGNode],
    edges: Dict[str, DKGEdge],
    clock_nets: set[str],
    reset_nets: set[str],
):
    for e in edges.values():
        # Clock tree
        if e.signal_name in clock_nets:
            e.flow_type = EdgeFlowType.CLOCK_TREE
            continue

        # Reset
        if e.signal_name in reset_nets:
            if is_active_low(e.signal_name):
                e.flow_type = EdgeFlowType.ASYNC_RESET
            else:
                e.flow_type = EdgeFlowType.ASYNC_RESET
            continue

        src = nodes[e.src_node]
        dst = nodes[e.dst_node]

        # Sequential boundary
        if src.entity_class == EntityClass.FLIP_FLOP:
            e.flow_type = EdgeFlowType.SEQ_LAUNCH
        elif dst.entity_class == EntityClass.FLIP_FLOP:
            e.flow_type = EdgeFlowType.SEQ_CAPTURE
        else:
            e.flow_type = EdgeFlowType.COMBINATIONAL
def assign_clock_domains(
    nodes: Dict[str, DKGNode],
    edges: Dict[str, DKGEdge],
    clock_nets: set[str],
):
    for n in nodes.values():
        if n.entity_class != EntityClass.FLIP_FLOP:
            continue

        for eid in n.in_edges:
            e = edges[eid]
            if e.signal_name in clock_nets:
                n.clock_domain = e.signal_name
                break

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
                edge_id=f"bus_e{new_eid}", #어차피 이 함수 끝에서 재생성 됨.
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
def cell_signature(cell: CellIR) -> str:
    ports = sorted(
        f"{p}:{cell.port_dirs[p]}:{len(bits)}"
        for p, bits in cell.connections.items()
    )
    return "|".join([
        cell.type,
        cell.module,
        ",".join(ports),
    ])
def signal_signature(e: DKGEdge) -> str:
    if e.bit_range:
        msb, lsb = e.bit_range
        return f"{e.signal_name}[{msb}:{lsb}]"
    return e.signal_name
def edge_signature(e: DKGEdge) -> str:
    return "|".join([
        e.src_node,
        e.dst_node,
        e.relation_type.value,
        e.flow_type.value,
        signal_signature(e),
    ])
def make_edge_id(e: DKGEdge) -> str:
    sig = edge_signature(e)
    h = stable_hash(sig)
    return f"E_{e.relation_type.value}_{h}"
import hashlib

def stable_hash(s: str, length=12) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:length]
nodes: dict[str, DKGNode] = {}

for cell in cells:
    sig = cell_signature(cell)
    nid = f"N_{map_cell_type(cell.type).value}_{stable_hash(sig)}"
    nodes[nid] = DKGNode(
        node_id=nid,
        entity_class=map_cell_type(cell.type),
        hier_path=cell.module,
        local_name=cell.name,
    )
    nodes[nid].canonical_name = make_node_canonical_name(nodes[nid])
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
new_edges = {}
for e in edges.values():
    new_id = make_edge_id(e)
    e.edge_id = new_id
    new_edges[new_id] = e

edges = new_edges
clock_nets, reset_nets = detect_clock_reset_signals(nodes, edges)

assign_clock_domains(nodes, edges, clock_nets)

assign_edge_flow_types(nodes, edges, clock_nets, reset_nets)
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
    canonical_name: Optional[str] = None          # "ALU combinational cloud"
    display_name: Optional[str] = None            # "ALU"


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
    canonical_name: Optional[str] = None          # "alu_out → ex_reg"
    display_name: Optional[str] = None            # "data[31:0]"

@dataclass
class SuperGraph:
    super_nodes: Dict[str, SuperNode]
    super_edges: Dict[Tuple[str, str], SuperEdge]
    node_to_super: Dict[str, str]
#endregion
#region ID Generation Helpers
def supernode_signature(
    view: GraphViewType,
    super_class: SuperClass,
    member_node_ids: set[str],
    policy_version: str = "v1"
) -> str:
    nodes_part = ",".join(sorted(member_node_ids))
    return "|".join([
        view.value,
        super_class.value,
        policy_version,
        nodes_part,
    ])
def make_supernode_id(
    view: GraphViewType,
    super_class: SuperClass,
    member_node_ids: set[str],
    policy_version: str = "v1"
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
    return "|".join([
        src_sn,
        dst_sn,
        policy_version,
        edges_part,
    ])
def make_superedge_id(
    src_sn: str,
    dst_sn: str,
    member_edge_ids: set[str],
    policy_version: str = "v1",
) -> str:
    sig = superedge_signature(src_sn, dst_sn, member_edge_ids, policy_version)
    h = stable_hash(sig)
    return f"SE_{h}"


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
            sn.canonical_name = make_supernode_canonical_name(sn, self.nodes)
            sn.display_name = make_supernode_display_name(sn)
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

            sn_id = make_supernode_id(
                view=self.view,
                super_class=SuperClass.COMB_CLOUD,
                member_node_ids=component,
                policy_version="v1"
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

    # -------- cycle 2.5 --------

    def cycle2_5_eliminate(self):
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
                    policy_version="v1"
                ),
                super_class=SuperClass.ELIMINATED,
                member_nodes={nid},
                member_edges=set(),
                )
            sn.canonical_name = make_supernode_canonical_name(sn, self.nodes)
            sn.display_name = make_supernode_display_name(sn)

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
                    self.super_nodes
                )
                self.super_edges[key].display_name = make_superedge_display_name(
                    self.super_edges[key]
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
