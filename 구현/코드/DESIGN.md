# DKG Multi-Stage Parsing 설계

## 개요

DKG는 여러 소스에서 점진적으로 정보를 수집하여 그래프를 구축합니다. 각 파싱 단계(stage)는 기존 그래프에 새로운 정보를 추가하거나 기존 정보를 확정합니다.

## 파싱 단계 (Parsing Stages)

```
1. RTL         → Yosys JSON (구조 정보, 추론된 clock/reset)
2. SYNTHESIS   → 합성 netlist (최종 구조)
3. CONSTRAINTS → SDC/XDC (명시적 clock, timing exception)
4. FLOORPLAN   → TCL/Pblock (물리적 배치)
5. TIMING      → 타이밍 리포트 (delay, slack)
6. BOARD       → BD file (보드 연결)
```

## 필드 출처 우선순위 (Field Source Priority)

각 필드는 출처에 따라 신뢰도가 다릅니다:

```
1. INFERRED (추론)        - 이름 패턴 등으로 추측
2. ANALYZED (분석)        - 도구가 분석한 결과
3. DECLARED (명시)        - 파일에서 명시적으로 선언
4. USER_OVERRIDE (사용자) - 사용자가 직접 설정
```

**업데이트 규칙**: 우선순위가 같거나 높은 경우에만 기존 값을 덮어씁니다.

## 예시: Clock Domain 업데이트

### Stage 1: RTL (Yosys)
```python
# 이름 기반 추론
if is_clock_name(signal.name):  # "clk" 패턴 감지
    node.clock_domain = signal.name
    metadata.set("clock_domain", signal.name, 
                 source=FieldSource.INFERRED,
                 stage=ParsingStage.RTL)
```

**상태**: `clock_domain = "clk"` (INFERRED)

### Stage 2: Constraints (SDC)
```tcl
create_clock -name sys_clk -period 10 [get_ports clk]
```

```python
# SDC 파서가 명시적 선언 발견
updater.update_node_field(
    node_id, "clock_domain", "sys_clk",
    source=FieldSource.DECLARED,
    stage=ParsingStage.CONSTRAINTS,
    origin_file="design.sdc",
    origin_line=5
)
```

**상태**: `clock_domain = "sys_clk"` (DECLARED) ✅ 업데이트됨!

### Stage 3: 사용자 오버라이드
```python
# 사용자가 GUI에서 수정
updater.update_node_field(
    node_id, "clock_domain", "my_custom_clk",
    source=FieldSource.USER_OVERRIDE,
    stage=ParsingStage.CONSTRAINTS
)
```

**상태**: `clock_domain = "my_custom_clk"` (USER_OVERRIDE) ✅ 업데이트됨!

## 사용 예시

### 기본 사용
```python
from dkg.pipeline import DKGPipeline
from dkg.config import YosysConfig

# 파이프라인 생성
config = YosysConfig(
    src_dir_win=r"C:\rtl",
    out_json_win=r"C:\design.json",
    top_module="top"
)
pipeline = DKGPipeline(config)

# Stage 1: RTL 파싱
pipeline.run_rtl_stage()

# Stage 2: 제약 추가
pipeline.add_constraints("design.sdc")   # SDC 파일
pipeline.add_constraints("pinout.xdc")   # XDC 파일

# Stage 3: 타이밍 추가
pipeline.add_timing_report("timing.rpt")

# 최종 그래프
nodes, edges = pipeline.get_graph()
```

### 고급 사용 (직접 업데이트)
```python
# GraphUpdater 직접 사용
updater = pipeline.get_updater()

# 특정 노드 필드 업데이트
updater.update_node_field(
    "N_FlipFlop_abc123",
    "clock_domain",
    "custom_clk",
    FieldSource.USER_OVERRIDE,
    ParsingStage.CONSTRAINTS
)

# 일괄 업데이트
clock_assignments = {
    "N_FlipFlop_1": "clk_a",
    "N_FlipFlop_2": "clk_b",
}
updater.batch_update_clock_domains(
    clock_assignments,
    FieldSource.DECLARED,
    ParsingStage.CONSTRAINTS
)
```

## 캐싱 전략

메타데이터를 활용한 스마트 캐싱:

```python
# 메타데이터 내보내기
metadata = pipeline.export_metadata()

# 캐시 저장
cache = {
    "graph": {"nodes": nodes, "edges": edges},
    "metadata": metadata,
    "completed_stages": pipeline.completed_stages,
    "timestamp": time.time()
}

# 캐시 검증
def is_cache_valid(cache, new_files):
    # SDC가 변경되었는지 확인
    if "design.sdc" in new_files:
        # CONSTRAINTS stage 이후 데이터는 무효화
        return ParsingStage.CONSTRAINTS not in cache["completed_stages"]
    return True
```

## 파서 추가 방법

새 제약 파일 형식을 추가하려면:

1. `ConstraintParser` 상속
2. `get_stage()` 구현 (어느 stage인지)
3. `parse_and_update()` 구현 (파싱 로직)
4. `DKGPipeline.parsers`에 등록

```python
class CustomParser(ConstraintParser):
    def get_stage(self) -> ParsingStage:
        return ParsingStage.CONSTRAINTS
    
    def parse_and_update(self, filepath, updater, nodes, edges):
        # 파싱 로직
        for line in open(filepath):
            # ...
            updater.update_node_field(...)
```

## 필드별 Stage 매핑

| 필드 | RTL | CONSTRAINTS | TIMING |
|------|-----|-------------|--------|
| `entity_class` | ✅ | - | - |
| `hier_path` | ✅ | - | - |
| `clock_domain` | 🔸 추론 | ✅ 확정 | - |
| `flow_type` | 🔸 추론 | ✅ 확정 | - |
| `timing_exception` | - | ✅ | - |
| `delay` | - | - | ✅ |
| `slack` | - | - | ✅ |

✅ 확정  
🔸 추론 (나중에 덮어쓰기 가능)  
\- 해당 없음

## 향후 확장

- [ ] 필드 변경 이력 추적
- [ ] 충돌 감지 (서로 다른 SDC에서 다른 값 선언)
- [ ] 부분 업데이트 (특정 노드만 재파싱)
- [ ] 파서 체인 병렬화
- [ ] JSON/DB로 메타데이터 직렬화
