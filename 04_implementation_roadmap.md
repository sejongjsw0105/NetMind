# FPGA AI 개발 도구 - 구현 로드맵

## 1. 개발 철학

### 1.1 점진적 개발 (Incremental Development)
- 각 버전은 **독립적으로 가치 제공**
- 이전 버전 위에 기능 추가
- 조기 피드백으로 방향 수정 가능

### 1.2 MVP 우선 (MVP-First)
- v0부터 실제 사용 가능한 도구
- 완벽함보다 **빠른 검증**
- 사용자 피드백 기반 개선

### 1.3 포트폴리오 전략
- .v, .sv만으로도 포트폴리오 가치 있음
- Yosys가 잘 구축되어 빠른 개발 가능
- 투자 유치/학술 발표용으로 충분

## 2. 버전별 로드맵

### v0 – 그래프 엔진 + 시각화 (3주)

#### 목표
최소 기능으로 **"작동하는 그래프 도구"** 구현

#### 기능
1. **파싱**:
   - Yosys로 RTL → 모듈 그래프 추출
   - Node: 모듈 인스턴스
   - Edge: 신호 연결

2. **그래프 구조**:
   - TOP에서 hop 기반 펼치기
   - 노드 클릭해서 하위 계층 열기

3. **시각화**:
   - 간단한 웹 UI (D3.js / Cytoscape.js)
   - 또는 Graphviz로 정적 그래프

#### 기술 스택
```python
# 파싱
yosys -p "read_verilog top.v; hierarchy -check; write_json design.json"

# 그래프 구축
import json
import networkx as nx

# 시각화 (옵션 1: Graphviz)
import graphviz

# 시각화 (옵션 2: 웹)
# Flask + D3.js
```

#### 산출물
- [ ] Yosys JSON → Python 그래프 변환기
- [ ] 기본 그래프 시각화
- [ ] README + 사용 예제

#### 성공 기준
- [ ] 100 라인 규모 RTL 프로젝트 시각화 가능
- [ ] 계층 구조 명확히 표현
- [ ] 3초 이내 로딩

---

### v1 – 신호/변수 검색 + 하이라이트 (2주)

#### 목표
사용자가 **특정 신호를 찾아 추적**할 수 있게

#### 기능
1. **검색**:
   - (signal_name, source_module) 기반 엣지 검색
   - 예: "data_valid in u_cpu"

2. **하이라이트**:
   - 검색 결과 엣지를 다른 색으로 표시
   - 해당 엣지의 source/sink 노드도 강조

3. **다중 결과 처리**:
   - 같은 이름 신호가 여러 모듈에 있을 때
   - 리스트로 보여주고 하나씩 필터링

#### UI 예시
```
[Search: data_valid]
Results:
 1. top.u_cpu.data_valid → top.u_memory
 2. top.u_io.data_valid → top.u_cpu
 
[선택] Result 1 → 그래프에서 하이라이트
```

#### 산출물
- [ ] 검색 엔진 (신호 이름 + 계층 경로)
- [ ] UI 검색창
- [ ] 하이라이트 기능

#### 성공 기준
- [ ] 1000개 신호 중 특정 신호 <1초 검색
- [ ] 시각적으로 명확한 하이라이트

---

### v2 – XDC/보드 정보 통합 (3주)

#### 목표
FPGA **물리적 제약** 정보를 그래프에 통합

#### 기능
1. **XDC 파싱**:
   - 핀 배치 (set_property PACKAGE_PIN)
   - 클럭 정의 (create_clock)
   - 타이밍 예외 (set_false_path, set_multicycle_path)

2. **그래프 통합**:
   - 핀/클럭/타이밍 예외를 노드/엣지 속성으로 부착
   - IO/Board 모듈 노드 추가

3. **전용 뷰**:
   - Clock Domain View (클럭 도메인별 색상)
   - IO Path View (IO 포트 → 내부 경로)

#### XDC 파싱 예시
```python
def parse_xdc(filepath):
    constraints = {}
    for line in open(filepath):
        if "set_property PACKAGE_PIN" in line:
            # port → pin 매핑 추출
            port, pin = extract_pin_mapping(line)
            constraints[port] = {"pin": pin}
        elif "create_clock" in line:
            # 클럭 정의 추출
            clock_name, period = extract_clock(line)
            constraints[clock_name] = {"period": period}
    return constraints
```

#### 산출물
- [ ] XDC 파서
- [ ] Physical View 구현
- [ ] Clock Domain 시각화

#### 성공 기준
- [ ] 실제 FPGA 프로젝트의 XDC 파싱 성공
- [ ] 클럭 도메인별 색상 구분 명확

---

### v3 – AI 컨텍스트 연동 (4주)

#### 목표
그래프를 **AI가 이해할 수 있는 형태**로 변환

#### 기능
1. **서브그래프 추출**:
   - 사용자가 영역 선택 또는 모듈 지정
   - 해당 영역 + N-hop 이내 노드/엣지 추출

2. **컨텍스트 패키징**:
   - 서브그래프를 JSON/텍스트로 변환
   - 관련 코드 조각 첨부
   - 관련 제약 (XDC) 포함

3. **LLM 연동**:
   - API 호출 (OpenAI, Claude, 온프레미스 LLM)
   - 질문 예: "이 path 설명해줘", "버그 가능성은?"

#### 컨텍스트 예시
```json
{
  "subgraph": {
    "nodes": [
      {"id": "N1", "name": "u_alu", "type": "Module"},
      {"id": "N2", "name": "u_regs", "type": "Module"}
    ],
    "edges": [
      {"src": "N1", "dst": "N2", "signal": "alu_result"}
    ]
  },
  "code": {
    "u_alu": "module alu(...); ... endmodule",
    "u_regs": "module regs(...); ... endmodule"
  },
  "constraints": {
    "clock": "create_clock -period 10 [get_ports clk]"
  }
}
```

#### AI 질의 예시
```python
context = extract_subgraph(selected_nodes, depth=2)
prompt = f"""
Given this FPGA design:
{context}

Question: Can you identify potential timing issues in this path?
"""
response = llm_api.chat(prompt)
```

#### 산출물
- [ ] 서브그래프 추출 엔진
- [ ] JSON 직렬화
- [ ] LLM API 연동
- [ ] 샘플 질의 템플릿

#### 성공 기준
- [ ] 1000 노드 그래프에서 10 노드 서브그래프 <1초 추출
- [ ] LLM이 유의미한 답변 생성 (정성 평가)

---

### v4 – 타이밍 리포트 연동 (3주)

#### 목표
실제 **타이밍 분석 결과**를 그래프에 표시

#### 기능
1. **타이밍 리포트 파싱**:
   - Vivado `report_timing` 결과 (.rpt) 파싱
   - Path별 delay, slack 추출

2. **그래프 부착**:
   - 각 엣지에 delay, slack 기록
   - Worst path 식별

3. **시각화**:
   - Critical path (slack < 0) → 빨간색
   - 여유 있는 path → 회색
   - 엣지 클릭 → "이 엣지가 포함된 worst path 3개" 표시

#### 타이밍 리포트 파싱 예시
```python
def parse_timing_report(filepath):
    paths = []
    current_path = None
    for line in open(filepath):
        if "Slack (MET)" in line or "Slack (VIOLATED)" in line:
            slack = extract_slack(line)
            current_path = {"slack": slack, "edges": []}
        elif "Location" in line:
            # 경로 상의 셀/넷 추출
            edge = extract_edge_from_line(line)
            current_path["edges"].append(edge)
        elif "---" in line and current_path:
            paths.append(current_path)
            current_path = None
    return paths
```

#### 산출물
- [ ] 타이밍 리포트 파서
- [ ] Timing View 구현
- [ ] Critical path 하이라이트

#### 성공 기준
- [ ] 실제 프로젝트의 타이밍 리포트 파싱 성공
- [ ] Critical path 시각적으로 명확히 구분

---

## 3. 기술 스택 정리

### 3.1 코어 라이브러리

| 목적 | 라이브러리 | 버전 |
|------|----------|------|
| 그래프 구조 | NetworkX | 3.0+ |
| 파싱 (RTL) | Yosys | latest |
| 파싱 (XDC/TCL) | 정규표현식 | stdlib |
| 시각화 | Cytoscape.js / D3.js | latest |
| 웹 프레임워크 | Flask / FastAPI | latest |

### 3.2 선택적 라이브러리

| 목적 | 라이브러리 | 사용 시점 |
|------|----------|----------|
| AI 연동 | openai / anthropic | v3+ |
| 데이터베이스 | SQLite / PostgreSQL | 대규모 프로젝트 |
| 캐싱 | Redis | 성능 최적화 필요 시 |

### 3.3 개발 환경

```bash
# Python 환경
python 3.10+

# 의존성
pip install networkx flask pydantic

# Yosys 설치 (Linux)
sudo apt-get install yosys

# Yosys 설치 (Windows)
# WSL 또는 Docker 사용 권장
```

---

## 4. 단계별 우선순위

### 포트폴리오용 (최소)
- ✅ v0: 그래프 시각화
- ✅ v1: 검색 기능
- ⚠️ v2: XDC 통합 (선택)

**충분한 가치**:
- 기술 검증
- 학술 발표 (논문/학회)
- 투자 유치 데모

### 실제 사용 가능 제품
- ✅ v0-v2: 기본 기능
- ✅ v3: AI 연동 (핵심 차별화)
- ⚠️ v4: 타이밍 분석 (부가 가치)

**시장 출시 가능**:
- 베타 테스터 확보
- 초기 고객 판매
- 피드백 수집

### 완성형 제품
- ✅ v0-v4 전체
- ✅ 성능 최적화
- ✅ 사용자 경험 개선
- ✅ 문서화

**M&A 대상**:
- EDA 툴 업체 관심
- IDE 통합 가능
- 특허 포트폴리오 완성

---

## 5. 개발 타임라인 (풀타임 기준)

### Phase 1: PoC (3개월)
```
Month 1: v0 개발 + 테스트
Month 2: v1 개발 + 피드백
Month 3: v2 개발 + 특허 준비
```

**마일스톤**:
- [ ] 100 라인 RTL 시각화
- [ ] 학교/연구실 피드백 수집
- [ ] 특허 명세서 초안

### Phase 2: MVP (3개월)
```
Month 4-5: v3 개발 (AI 연동)
Month 6: 베타 테스트 + 개선
```

**마일스톤**:
- [ ] 실제 프로젝트 (1000+ 라인) 지원
- [ ] 베타 테스터 10명 확보
- [ ] 투자 자료 준비

### Phase 3: 시장 진입 (6개월)
```
Month 7-9: v4 + 성능 최적화
Month 10-12: 초기 고객 지원 + 마케팅
```

**마일스톤**:
- [ ] 상용 제품 출시
- [ ] 초기 고객 5곳 확보
- [ ] EDA 업체 컨택

---

## 6. 위험 관리

### 6.1 기술적 위험

| 위험 | 완화 전략 |
|------|----------|
| Yosys 파싱 실패 | SystemVerilog → Verilog 변환 |
| 대규모 프로젝트 성능 | 레이지 로딩, 캐싱 |
| XDC 파싱 오류 | 주요 명령어만 지원, 점진적 확장 |

### 6.2 일정 위험

| 위험 | 완화 전략 |
|------|----------|
| v3 개발 지연 | v2까지만으로 MVP 가능 |
| 타이밍 파싱 복잡 | v4를 선택 기능으로 |
| 사용자 피드백 부족 | 베타 테스터 조기 확보 |

### 6.3 시장 위험

| 위험 | 완화 전략 |
|------|----------|
| 대기업 자체 개발 | 빠른 개발 + 특허 선점 |
| 보수적 시장 | 학계 루트 활용 |
| 경쟁 제품 출현 | 기술적 차별화 강화 |

---

## 7. 측정 지표 (KPI)

### 기술 지표
- [ ] 파싱 성공률 (RTL)
- [ ] 파싱 시간 (1000 라인당)
- [ ] 그래프 로딩 시간
- [ ] 메모리 사용량

### 사용자 지표
- [ ] 베타 테스터 수
- [ ] 사용 빈도 (주당 사용 횟수)
- [ ] 피드백 만족도 (1-5점)

### 비즈니스 지표
- [ ] 초기 고객 수
- [ ] 라이선스 판매액
- [ ] M&A 문의 수

---

## 8. 다음 단계 (v5+)

### v5 – SystemVerilog 완전 지원
- 인터페이스, 구조체, 클래스 지원
- Assertion 파싱

### v6 – 시뮬레이션 연동
- VCD/FSDB 파일 파싱
- 신호 파형 시각화

### v7 – 협업 기능
- 다중 사용자 실시간 편집
- 주석/댓글 기능

### v8 – 자동 최적화 제안
- AI가 타이밍 개선 방법 제안
- 리팩토링 추천

---

## 9. 최소 실행 계획 (파트타임 기준)

### 4개월 계획 (주 20시간)
```
Month 1: v0 (그래프 엔진)
Month 2: v1 (검색 기능)
Month 3: v2 (XDC 통합) - 기본만
Month 4: 문서화 + 포트폴리오 준비
```

**목표**: 학술 발표 또는 대학원 프로젝트로 활용

### 성공 정의
- [ ] GitHub 저장소 공개
- [ ] README + 사용 예제
- [ ] 학회 발표 또는 블로그 포스트
- [ ] 교수님/동료 피드백

---

## 10. 체크리스트 (개발 시작 전)

### 환경 설정
- [ ] Python 3.10+ 설치
- [ ] Yosys 설치 확인
- [ ] GitHub 저장소 생성
- [ ] 개발 환경 (VSCode + 확장 프로그램)

### 샘플 데이터
- [ ] 간단한 RTL 프로젝트 (100 라인)
- [ ] XDC 파일 샘플
- [ ] 타이밍 리포트 샘플

### 학습
- [ ] Yosys 문서 읽기
- [ ] NetworkX 튜토리얼
- [ ] D3.js / Cytoscape.js 예제

---

## 11. 최종 권장 사항

### 시작하기
1. **v0부터 시작** (완벽주의 버리기)
2. **조기 피드백** (주변 사람들에게 보여주기)
3. **문서화 습관** (README 먼저 쓰기)

### 확장하기
1. **사용자 중심** (기능보다 문제 해결)
2. **점진적 개선** (한 번에 하나씩)
3. **데이터 기반** (사용 로그 수집)

### 상용화하기
1. **빠른 엑싯** (완벽한 제품보다 타이밍)
2. **네트워크 활용** (교수님, 동문)
3. **특허 선점** (기술 문서화)
