#region Parser
#region Yosys HDL Parser for WSL
import subprocess
import glob
import os
from pathlib import Path

# ================== 설정 ==================
SRC_DIR_WIN = r"C:\Users\User\Desktop\NetMind\구현\예시"     # Windows 경로
OUT_JSON_WIN = r"C:\Users\User\Desktop\NetMind\구현\design.json"
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
    drivers: list[str] = field(default_factory=list)  # node_id
    loads: list[str] = field(default_factory=list)

@dataclass
class CellIR:
    name: str
    type: str
    module: str
    port_dirs: dict[str, str]
    connections: dict[str, list[int]]
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
        for wid in netinfo["bits"]:
            w = get_wire(wid)
            if w:
                w.name = netname
cells: list[CellIR] = []

for mod_name, mod in yosys["modules"].items():
    for cname, c in mod.get("cells", {}).items():
        cells.append(CellIR(
            name=cname,
            type=c["type"],
            module=mod_name,
            port_dirs=c["port_directions"],
            connections=c["connections"]
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

    # Abstract control
    CLOCK_DOMAIN = "ClockDomain"
    RESET_DOMAIN = "ResetDomain"
@dataclass
class DKGNode:
    node_id: str                     # canonical unique ID
    entity_class: EntityClass
    hier_path: str                   # top.u1.u2
    local_name: str                  # e.g., u_core
    view: str                        # structural / netlist / physical ...

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
    parameters: Dict[str, str] = field(default_factory=dict)

    # ---- Timing ----
    delay: Optional[float] = None
    arrival_time: Optional[float] = None
    required_time: Optional[float] = None
    slack: Optional[float] = None

    # ---- Misc ----
    attributes: Dict[str, str] = field(default_factory=dict)
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
        view="netlist",
    )
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

            nodes[src].out_edges.append(edge_id)
            nodes[dst].in_edges.append(edge_id)
#endregion
#region Output Summary
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
