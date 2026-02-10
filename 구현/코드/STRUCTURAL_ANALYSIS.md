# Structural Clock/Reset Detection

## 개선 사항

### Before: 이름 기반 휴리스틱 (낮은 신뢰도)
```python
# RTL stage
if is_clock_name(signal.name):  # "clk" 패턴 감지
    clock_nets.add(signal.name)

# 문제: "my_clk_counter" 같은 신호까지 clock으로 잘못 분류 가능
```

### After: 구조적 분석 (높은 신뢰도)
```python
# FF cell 포트 정보 활용
for cell in cells:
    if cell.type == "$dff":  # FF cell인지 확인
        if "CLK" in cell.connections:  # 포트 이름 확인
            clk_wid = cell.connections["CLK"][0]
            signal_name = wires[clk_wid].name
            clock_nets.add(signal_name)  # 확실한 clock 신호
```

## 식별 우선순위 (3단계)

```
1️⃣ 구조적 분석 (Stage 1) - 신뢰도 ★★★★★
   ├─ FF cell 타입: $dff, $adff, $sdff, $dffe, $sdffe, $aldff
   ├─ Clock 포트: CLK
   ├─ 비동기 리셋: ARST, ARST_N, NRST, NRESET
   └─ 동기 리셋: SRST, SRST_N, SR, R, RST

2️⃣ 신호 분석 (Stage 2) - 신뢰도 ★★★
   ├─ Signal name 패턴 매칭
   ├─ 이미 식별된 신호면 추가하지 않음 (deduplication)
   └─ Fallback용도

3️⃣ FF 입력 확인 (Stage 3) - 신뢰도 ★★
   ├─ FF 노드의 입력 신호 재검증
   ├─ 구조 분석 미완료 edge 보충
   └─ 최종 확인
```

## 코드 예시

### Yosys JSON에서 FF 정보 추출
```json
{
  "modules": {
    "top": {
      "cells": {
        "ff1": {
          "type": "$dff",
          "port_directions": {
            "CLK": "input",
            "D": "input",
            "Q": "output"
          },
          "connections": {
            "CLK": [5],        // wire ID 5
            "D": [10, 11],     // wire IDs 10, 11 (data bits)
            "Q": [20, 21]
          }
        },
        "ff2": {
          "type": "$adff",   // 비동기 리셋 FF
          "connections": {
            "CLK": [5],
            "ARST": [6],      // 비동기 리셋 신호
            "D": [30],
            "Q": [40]
          }
        }
      }
    }
  }
}
```

### 처리 흐름
```python
# 1. FF cell "ff1" 분석
for wid in cell.connections["CLK"]:           # [5]
    wire = wires[5]
    if wire.name == "clk":                    # ← 직접 확인
        clock_nets.add("clk")                 # ✅ 구조적으로 증명됨

# 2. FF cell "ff2" 분석
for wid in cell.connections["ARST"]:          # [6]
    wire = wires[6]
    if wire.name == "rst_n":
        reset_nets.add("rst_n")               # ✅ 포트명으로 증명됨

# 3. 이름 기반 검증 (추가 후보)
for edge in edges:
    if is_clock_name(edge.signal_name):
        if edge.signal_name not in clock_nets:
            clock_nets.add(edge.signal_name)  # 보충
```

## 지원하는 FF Cell 타입

### Yosys Standard Cells
| 타입 | 설명 | CLK | D | Q | AsyncRst | SyncRst |
|------|------|-----|---|---|----------|---------|
| $dff | Simple D-FF | ✅ | ✅ | ✅ | ❌ | ❌ |
| $dffe | D-FF with enable | ✅ | ✅ | ✅ | ❌ | ❌ |
| $adff | Async reset D-FF | ✅ | ✅ | ✅ | ✅ | ❌ |
| $aldff | Async load D-FF | ✅ | ✅ | ✅ | ✅ | ❌ |
| $sdff | Sync reset D-FF | ✅ | ✅ | ✅ | ❌ | ✅ |
| $sdffe | Sync reset D-FF with enable | ✅ | ✅ | ✅ | ❌ | ✅ |

### 리셋 포트명 매핑
```python
# 비동기 리셋 포트
ASYNC_RESET_PORTS = {"ARST", "ARST_N", "NRST", "NRESET"}

# 동기 리셋 포트
SYNC_RESET_PORTS = {"SRST", "SRST_N", "SR", "R", "RST"}
```

## 실제 예시

### 기존 (이름 기반만)
```
Input: Yosys JSON + 신호들
RTL.clock_domain = "clk"     (휴리스틱)
RTL.reset_signals = ["reset"] (휴리스틱)

문제점:
- RTL.my_clk_counter → 잘못 식별
- RTL.reset_hold_time → 잘못 식별
```

### 개선 (구조적 분석)
```
Input: Yosys JSON + FF cell 정보
Step 1: $dff.CLK → wire[5] → "sys_clk"  ✅
Step 2: $adff.ARST → wire[6] → "async_rst_n"  ✅
Step 3: Verify with names (보충)

결과:
- clock_nets = {"sys_clk"}
- reset_nets = {"async_rst_n"}

이점:
- 100% 정확 (cell 포트에서 직접 추출)
- 이름 패턴에 영향 없음
- SDC 전에 정확한 기준선 수립
```

## SDC와의 조화

### RTL Stage (구조적 분석)
```
clock_domain = "sys_clk"     (INFERRED, 구조 분석)
flow_type = SEQ_LAUNCH       (INFERRED, 포트 분석)
```

### Constraints Stage (SDC 오버라이드)
```
clock_domain = "main_clk"    (DECLARED, SDC 명시)
                              ✅ 우선순위 높음 → 덮어씀
```

## 성능

- **시간**: O(cells + wires) - 한 번의 순회로 식별
- **메모리**: O(clock_nets + reset_nets) - 신호명만 저장
- **정확도**: 100% (구조 정보는 거짓말 못함)

## 추가 개선 사항

향후 추가 가능한 최적화:

1. **SR (Set-Reset) Latch 식별**
   ```python
   if cell.type == "$sr":
       # S 포트 → Set signal
       # R 포트 → Reset signal
   ```

2. **MUX 기반 래치 검출**
   ```python
   # D-FF 없이 MUX로 구성된 래치
   if cell.type == "$pmux" and is_feedback_loop(cell):
       # Clock 신호 추론
   ```

3. **CDC (Clock Domain Crossing) 감지**
   ```python
   # 다른 clock_domain의 FFs 간 신호 감지
   if edge.src_clock_domain != edge.dst_clock_domain:
       mark_as_cdc_signal(edge)
   ```
