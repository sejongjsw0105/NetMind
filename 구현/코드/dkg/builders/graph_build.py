from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

from ..core.graph import (
    DKGEdge,
    DKGNode,
    EdgeFlowType,
    EntityClass,
    RelationType,
    make_node_canonical_name,
)
from ..core.ir import CellIR, Wire
from ..core.provenance import Provenance, add_provenance, merge_provenances_edges
from ..utils import (
    is_active_low,
    is_clock_name,
    is_reset_name,
    parse_src,
    split_signal_bit,
    stable_hash,
)


def get_wire(wires: Dict[int, Wire], wid) -> Optional[Wire]:
    if isinstance(wid, str):
        return None
    if wid not in wires:
        wires[wid] = Wire(wid)
    return wires[wid]


def build_wires_and_cells(yosys: dict) -> Tuple[Dict[int, Wire], List[CellIR]]:
    wires: Dict[int, Wire] = {}
    cells: List[CellIR] = []

    for mod in yosys.get("modules", {}).values():
        for netname, netinfo in mod.get("netnames", {}).items():
            src = netinfo.get("src")
            for wid in netinfo.get("bits", []):
                w = get_wire(wires, wid)
                if w:
                    w.name = netname
                    w.src = src

    for mod_name, mod in yosys.get("modules", {}).items():
        for cname, c in mod.get("cells", {}).items():
            cells.append(
                CellIR(
                    name=cname,
                    type=c["type"],
                    module=mod_name,
                    port_dirs=c["port_directions"],
                    connections=c["connections"],
                    src=c.get("src"),
                )
            )

    return wires, cells


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
    return "|".join(
        [
            cell.type,
            cell.module,
            ",".join(ports),
        ]
    )


def signal_signature(e: DKGEdge) -> str:
    if e.bit_range:
        msb, lsb = e.bit_range
        return f"{e.signal_name}[{msb}:{lsb}]"
    return e.signal_name


def edge_signature(e: DKGEdge) -> str:
    return "|".join(
        [
            e.src_node,
            e.dst_node,
            e.relation_type.value,
            e.flow_type.value,
            signal_signature(e),
        ]
    )


def make_edge_id(e: DKGEdge) -> str:
    sig = edge_signature(e)
    h = stable_hash(sig)
    return f"E_{e.relation_type.value}_{h}"


def make_node_id(cell: CellIR) -> str:
    sig = cell_signature(cell)
    return f"N_{map_cell_type(cell.type).value}_{stable_hash(sig)}"


def connect_wires_to_cells(wires: Dict[int, Wire], cells: Iterable[CellIR]) -> None:
    cell_id_map: Dict[str, str] = {}
    for cell in cells:
        cell_key = f"{cell.module}.{cell.name}"
        cell_id_map[cell_key] = make_node_id(cell)

    for cell in cells:
        node_id = cell_id_map[f"{cell.module}.{cell.name}"]
        for port, bits in cell.connections.items():
            direction = cell.port_dirs[port]
            for wid in bits:
                w = get_wire(wires, wid)
                if not w:
                    continue
                if direction == "output":
                    w.drivers.append(node_id)
                else:
                    w.loads.append(node_id)


def detect_clock_reset_from_ff_cells(
    cells: List[CellIR],
    wires: Dict[int, Wire],
) -> Tuple[set[str], set[str]]:
    """
    Yosys FF cell 포트 정보에서 clock/reset 신호 직접 추출.
    
    구조적 분석을 통해 신뢰도 높은 식별:
    - $dff, $adff, $sdff 등의 CLK 포트 → clock
    - ARST, SRST 포트 → reset
    """
    clock_nets: set[str] = set()
    reset_nets: set[str] = set()
    
    # FF cell 타입 정의
    ff_cell_types = {
        "$dff", "$adff", "$sdff",
        "$dffe", "$sdffe", "$aldff", "$aldffe",
    }
    
    for cell in cells:
        if cell.type not in ff_cell_types:
            continue
        
        # CLK 포트 찾기
        if "CLK" in cell.connections:
            clk_wids = cell.connections["CLK"]
            for wid in clk_wids:
                w = get_wire(wires, wid)
                if w and w.name:
                    clock_nets.add(w.name)
        
        # 비동기 리셋 포트 (ARST, ARST_N 등)
        async_reset_ports = {"ARST", "ARST_N", "NRST", "NRESET"}
        for port in async_reset_ports:
            if port in cell.connections:
                rst_wids = cell.connections[port]
                for wid in rst_wids:
                    w = get_wire(wires, wid)
                    if w and w.name:
                        reset_nets.add(w.name)
        
        # 동기 리셋 포트 (SRST, SRST_N 등)
        sync_reset_ports = {"SRST", "SRST_N", "SR", "R", "RST"}
        for port in sync_reset_ports:
            if port in cell.connections:
                rst_wids = cell.connections[port]
                for wid in rst_wids:
                    w = get_wire(wires, wid)
                    if w and w.name:
                        reset_nets.add(w.name)
    
    return clock_nets, reset_nets


def detect_clock_reset_signals(
    nodes: Dict[str, DKGNode],
    edges: Dict[str, DKGEdge],
    cells: List[CellIR],
    wires: Dict[int, Wire],
) -> Tuple[set[str], set[str]]:
    """
    Clock/Reset 신호 식별 (다단계 우선순위).
    
    1️⃣ 구조적 분석: FF cell 포트 정보 (높은 신뢰도)
    2️⃣ 신호 분석: edge의 flow 정보
    3️⃣ 이름 기반 휴리스틱: 패턴 매칭 (낮은 신뢰도)
    """
    # Stage 1: 구조적 분석 (FF cell 포트)
    clock_nets, reset_nets = detect_clock_reset_from_ff_cells(cells, wires)
    
    # Stage 2: 엣지 신호 이름 기반 (추론)
    for e in edges.values():
        if is_clock_name(e.signal_name):
            clock_nets.add(e.signal_name)
        if is_reset_name(e.signal_name):
            reset_nets.add(e.signal_name)
    
    # Stage 3: FF 입력 신호 확인 (구조적 재검증)
    for n in nodes.values():
        if n.entity_class != EntityClass.FLIP_FLOP:
            continue
        for eid in n.in_edges:
            e = edges[eid]
            # 이미 식별된 것은 확인, 아니면 추가 확인
            if is_clock_name(e.signal_name) and e.signal_name not in clock_nets:
                clock_nets.add(e.signal_name)
            if is_reset_name(e.signal_name) and e.signal_name not in reset_nets:
                reset_nets.add(e.signal_name)
    
    return clock_nets, reset_nets


def assign_edge_flow_types(
    nodes: Dict[str, DKGNode],
    edges: Dict[str, DKGEdge],
    clock_nets: set[str],
    reset_nets: set[str],
) -> None:
    for e in edges.values():
        if e.signal_name in clock_nets:
            e.flow_type = EdgeFlowType.CLOCK_TREE
            continue
        if e.signal_name in reset_nets:
            e.flow_type = EdgeFlowType.ASYNC_RESET
            continue

        src = nodes[e.src_node]
        dst = nodes[e.dst_node]

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
) -> None:
    for n in nodes.values():
        if n.entity_class != EntityClass.FLIP_FLOP:
            continue
        for eid in n.in_edges:
            e = edges[eid]
            if e.signal_name in clock_nets:
                n.clock_domain = e.signal_name
                break


def merge_bit_edges_to_bus(edges: Dict[str, DKGEdge]) -> Dict[str, DKGEdge]:
    groups: Dict[Tuple[str, str, RelationType, EdgeFlowType, str], List[Tuple[Optional[int], DKGEdge]]] = defaultdict(list)

    for e in edges.values():
        base, bit = split_signal_bit(e.signal_name)
        key = (e.src_node, e.dst_node, e.relation_type, e.flow_type, base)
        groups[key].append((bit, e))

    new_edges: Dict[str, DKGEdge] = {}
    new_eid = 0

    for key, items in groups.items():
        _, _, _, _, base = key

        if all(bit is None for bit, _ in items):
            for _, e in items:
                new_edges[e.edge_id] = e
            continue

        items.sort(key=lambda x: (-1 if x[0] is None else x[0]))

        current_bucket: List[Tuple[Optional[int], DKGEdge]] = []
        prev_bit: Optional[int] = None

        def flush_bucket(bucket: List[Tuple[Optional[int], DKGEdge]]) -> None:
            nonlocal new_eid
            if not bucket:
                return

            bits = [b for b, _ in bucket if b is not None]
            edges_in_bucket = [e for _, e in bucket]

            if len(bits) <= 1:
                e = edges_in_bucket[0]
                new_edges[e.edge_id] = e
                return

            msb = max(bits)
            lsb = min(bits)
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
                primary_provenance=None,
            )

            primary, provs = merge_provenances_edges(edges_in_bucket)
            merged.provenances = provs
            merged.primary_provenance = primary
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


def reindex_node_edges(nodes: Dict[str, DKGNode], edges: Dict[str, DKGEdge]) -> None:
    for n in nodes.values():
        n.in_edges = []
        n.out_edges = []

    for e in edges.values():
        nodes[e.src_node].out_edges.append(e.edge_id)
        nodes[e.dst_node].in_edges.append(e.edge_id)


def build_nodes_and_edges(
    wires: Dict[int, Wire],
    cells: List[CellIR],
) -> Tuple[Dict[str, DKGNode], Dict[str, DKGEdge]]:
    connect_wires_to_cells(wires, cells)

    nodes: Dict[str, DKGNode] = {}
    for cell in cells:
        node_id = make_node_id(cell)
        node = DKGNode(
            node_id=node_id,
            entity_class=map_cell_type(cell.type),
            hier_path=cell.module,
            local_name=cell.name,
        )
        node.canonical_name = make_node_canonical_name(node)

        file, line = parse_src(cell.src)
        prov = Provenance(
            origin_file=file,
            origin_line=line,
            tool_stage="rtl",
            confidence="exact",
        )
        add_provenance(node, prov, make_primary=True)
        nodes[node_id] = node

    edges: Dict[str, DKGEdge] = {}
    eid = 0

    for w in wires.values():
        for src in w.drivers:
            for dst in w.loads:
                edge_id = f"e{eid}"
                eid += 1

                edge = DKGEdge(
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
                    confidence="exact",
                )
                add_provenance(edge, prov, make_primary=True)

                edges[edge_id] = edge

    edges = merge_bit_edges_to_bus(edges)

    new_edges: Dict[str, DKGEdge] = {}
    for e in edges.values():
        new_id = make_edge_id(e)
        e.edge_id = new_id
        new_edges[new_id] = e

    edges = new_edges
    reindex_node_edges(nodes, edges)

    clock_nets, reset_nets = detect_clock_reset_signals(nodes, edges, cells, wires)
    assign_clock_domains(nodes, edges, clock_nets)
    assign_edge_flow_types(nodes, edges, clock_nets, reset_nets)

    return nodes, edges
