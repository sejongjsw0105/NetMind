# DKG (Design Knowledge Graph)

하드웨어 디자인을 그래프로 표현하고 분석하는 도구입니다.

## 주요 기능

- **RTL 파싱**: Yosys를 통한 RTL(Verilog/SystemVerilog) 디자인 파싱
- **제약 조건 통합**: SDC/XDC 파일 파싱 및 적용
- **타이밍 분석**: 타이밍 리포트 통합 및 분석
- **SuperGraph**: 다양한 추상화 레벨의 그래프 뷰 생성
- **Query API**: 강력한 그래프 검색 및 분석 인터페이스
- **Web Viewer**: Cytoscape.js 기반 인터랙티브 웹 시각화

## 빠른 시작

### 1. Query API 사용 (Python)

```python
from dkg.pipeline import DKGPipeline
from dkg.utils.config import YosysConfig

# 설정
config = YosysConfig(
    src_dir_win=r"C:\path\to\rtl",
    out_json_win=r"C:\path\to\output.json",
    top_module="top_module_name"
)

# 파이프라인 실행
pipeline = DKGPipeline(config)
pipeline.run_rtl_stage()

# 그래프 가져오기
nodes, edges = pipeline.get_graph()
```

### 2. Web Viewer 사용

```bash
# 필수 패키지 설치
pip install -r requirements.txt

# 웹 서버 실행
python web_server.py

# 브라우저에서 열기
# http://localhost:5000
```

### 2. Query API 사용

```python
from dkg.query_api import create_query
from dkg.core.graph import EntityClass

# Query API 생성
query = create_query(nodes, edges)

# 모든 Flip-Flop 찾기
ffs = query.find_nodes(entity_class=EntityClass.FLIP_FLOP)

# Critical 노드 찾기
critical = query.find_critical_nodes(slack_threshold=0.0)

# 경로 탐색
paths = query.find_paths("node1", "node2", max_depth=10)

# 팬아웃 분석
fanout = query.get_fanout("clk_buf", max_depth=1)
```

### 3. 실행

```bash
python main.py
```

## 문서

- **[QUERY_API_GUIDE.md](QUERY_API_GUIDE.md)**: Query API 상세 사용 가이드
- **[DESIGN.md](DESIGN.md)**: DKG 설계 문서
- **[IMPLEMENTATION_COMPLETE.md](IMPLEMENTATION_COMPLETE.md)**: 구현 완료 보고서

## Query API 주요 기능

### 노드 검색
```python
# Entity class로 검색
ffs = query.find_nodes(entity_class=EntityClass.FLIP_FLOP)

# 이름 패턴으로 검색
clk_nodes = query.find_nodes(name_pattern="*clk*")

# 계층 구조로 검색
cpu_nodes = query.find_nodes(hierarchy_prefix="cpu")

# Slack 범위로 검색
critical = query.find_nodes(slack_range=(-float('inf'), 0.0))
```

### 경로 탐색
```python
# 모든 경로 찾기
paths = query.find_paths("start", "end", max_depth=10)

# 최단 경로
shortest = query.find_shortest_path("start", "end", weight="hops")

# 팬아웃 분석
fanout = query.get_fanout("node_id", max_depth=1)
```

### 타이밍 분석
```python
# Critical 노드
critical = query.find_critical_nodes(slack_threshold=0.0)

# 타이밍 요약
summary = query.get_timing_summary()
print(f"Worst slack: {summary.worst_slack}")
print(f"Violations: {summary.timing_violations}")
```

### 통계
```python
stats = query.get_statistics()
print(f"Total nodes: {stats['total_nodes']}")
print(f"Total edges: {stats['total_edges']}")
```

## 예시 실행

```bash
# Query API 예시
python -m dkg.query_api_example

# 메인 파이프라인 (디자인 필요)
python main.py
```

## 프로젝트 구조

```
.
├── dkg/
│   ├── core/           # 핵심 데이터 구조 (Node, Edge, IR)
│   ├── builders/       # 그래프 빌더 및 SuperGraph
│   ├── parsers/        # 파일 파서들 (Yosys, SDC, XDC 등)
│   ├── pipeline/       # 파이프라인 및 스테이지 관리
│   ├── timing/         # 타이밍 분석 및 통합
│   ├── utils/          # 유틸리티 함수
│   ├── query_api.py    # Query API
│   └── query_api_example.py  # Query API 예시
├── main.py             # 메인 실행 파일
└── QUERY_API_GUIDE.md  # Query API 상세 가이드
```

## 요구사항

- Python 3.8+
- Yosys (RTL 파싱용)
- Optional: matplotlib (시각화용)
- Optional: networkx (그래프 분석용)

## 기여

이 프로젝트는 하드웨어 디자인 분석 및 최적화를 위한 연구 프로젝트입니다.

## 라이선스

내부 사용
