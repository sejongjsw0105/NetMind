# DKG Web Viewer - 고급 기능 가이드

DKG Web Viewer의 10가지 고급 기능에 대한 상세 가이드입니다.

## 목차
1. [홉 제한 (Hop Limitation)](#1-홉-제한)
2. [내부 보기 (Internal View)](#2-내부-보기)
3. [확장된 노드 정보 (Extended Node Info)](#3-확장된-노드-정보)
4. [슈퍼노드 필터 (SuperNode Filter)](#4-슈퍼노드-필터)
5. [쿼리 터미널 (Query Terminal)](#5-쿼리-터미널)
6. [View & Context 전환](#6-view--context-전환)
7. [Cross-Probing (RTL 추적)](#7-cross-probing)
8. [미니맵 (Minimap)](#8-미니맵)
9. [내보내기 (Export)](#9-내보내기)
10. [Critical Path 하이라이팅](#10-critical-path-하이라이팅)

---

## 1. 홉 제한 (Hop Limitation)

**기능**: 특정 노드를 중심으로 N-홉 이내의 노드만 표시

### 사용법
1. 노드를 **더블클릭** (Double-tap)
2. 홉 개수 입력 (1-5)
3. 선택된 홉 범위 내 노드만 표시, 나머지는 숨김

### 동작 원리
```javascript
// 더블클릭 이벤트
cy.on('dbltap', 'node', onNodeDoubleTap);

// API 호출
GET /api/node/<node_id>/hop_limited?hops=2
```

### 되돌리기
```javascript
resetHopFilter(); // 툴바의 "Show All" 버튼
```

---

## 2. 내부 보기 (Internal View)

**기능**: SuperNode 내부의 DKGNode와 DKGEdge를 새 창에서 시각화

### 사용법
1. 노드를 **우클릭** (Right-click)
2. 컨텍스트 메뉴에서 "📦 내부 보기" 선택
3. 새 브라우저 창에 내부 그래프 표시

### 컨텍스트 메뉴
- 📦 **내부 보기**: SuperNode의 구성 노드 표시
- 🔍 **주변 보기**: 팬인/팬아웃 노드 표시
- 🛤️ **경로 추적**: 특정 노드까지의 경로 탐색

### API 엔드포인트
```http
GET /api/node/<node_id>/internal

Response:
{
  "nodes": [...],
  "edges": [...],
  "supernode_id": "sn_001",
  "super_class": "FunctionalUnit"
}
```

---

## 3. 확장된 노드 정보 (Extended Node Info)

**기능**: 좌클릭 시 노드의 상세 정보 + Analysis 데이터 + Provenance 표시

### 표시 정보
- **Basic Info**: Entity Class, Hierarchy, Slack, Timing
- **Fanout/Fanin**: 팬아웃/팬인 개수
- **Analysis**: SuperNode에 부착된 분석 결과
- **Provenance**: RTL 소스 코드 위치

### 사용법
1. 노드를 **좌클릭**
2. 우측 정보 패널에 상세 정보 표시
3. "📄 View Source Code" 클릭 → Provenance 확인

### API
```http
GET /api/node/<node_id>           # 기본 정보
GET /api/node/<node_id>/analysis  # Analysis 데이터
```

---

## 4. 슈퍼노드 필터 (SuperNode Filter)

**기능**: 특정 SuperNode 선택 시 관련 노드만 강조, 나머지 반투명화

### 사용법
1. 사이드바 → 필터 탭
2. "SuperNode Filter" 선택 박스에서 원하는 SuperNode 선택 (다중 선택 가능)
3. 선택되지 않은 노드는 opacity 0.2로 흐리게 표시

### CSS 스타일
```css
.dimmed {
    opacity: 0.2;
}
```

### API
```http
GET /api/supernodes

Response:
{
  "supernodes": [
    {"id": "sn_001", "super_class": "FunctionalUnit", "node_count": 42},
    ...
  ]
}
```

---

## 5. 쿼리 터미널 (Query Terminal)

**기능**: 자연어 쿼리로 그래프 검색 및 분석

### 지원 쿼리
- `show flip flops` - FlipFlop 노드 표시
- `find critical nodes` - Critical 노드 검색
- `path statistics` - 경로 통계 표시

### 사용법
1. 화면 하단 터미널 패널
2. 쿼리 입력 후 Enter
3. 결과가 터미널에 출력되고 그래프에 하이라이트

### API
```http
POST /api/query
Content-Type: application/json

{
  "query": "show flip flops"
}
```

### 터미널 명령어
```bash
> show flip flops
Found 127 nodes

> find critical nodes
Found 23 critical nodes

> path statistics
Total nodes: 5423, Total edges: 12847
```

---

## 6. View & Context 전환

**기능**: Design/Simulation 모드와 Structural/Connectivity/Physical 뷰 전환

### 툴바 컨트롤
```html
<!-- Context Toggle -->
[Design | Simulation]

<!-- View Select -->
<select>
  <option>Structural</option>
  <option>Connectivity</option>
  <option>Physical</option>
</select>
```

### 사용법
1. 툴바 상단의 Context 토글 버튼 클릭
2. View 드롭다운에서 원하는 뷰 선택
3. 그래프 자동 리로드

### API
```http
GET /api/views

Response:
{
  "views": ["Structural", "Connectivity", "Physical"],
  "contexts": ["Design", "Simulation"]
}
```

---

## 7. Cross-Probing (RTL 추적)

**기능**: 노드의 Provenance 정보로 RTL 소스 코드 역추적

### 표시 정보
- **파일명**: cpu.v
- **라인 번호**: 142
- **컬럼**: 15
- **코드 컨텍스트**: 해당 라인 주변 코드

### 사용법
1. 노드 좌클릭 → 정보 패널
2. "📄 View Source Code" 클릭
3. 모달 창에 소스 코드 표시

### Provenance 구조
```python
class Provenance:
    source_file: str      # "cpu.v"
    line_number: int      # 142
    column_number: int    # 15
    context: str          # 주변 코드
```

### API
```http
GET /api/node/<node_id>/provenance

Response:
{
  "node_id": "n_001",
  "provenance": {
    "file": "cpu.v",
    "line": 142,
    "column": 15,
    "context": "always @(posedge clk) begin\n  ..."
  }
}
```

---

## 8. 미니맵 (Minimap)

**기능**: 전체 그래프의 축소판 + 현재 뷰포트 위치 표시

### 위치
- 화면 우측 하단
- 터미널 위
- 200x150px

### 표시 요소
- 전체 노드 (파란색 점)
- 현재 뷰포트 (빨간색 박스)

### 구현
```javascript
function updateMinimap(canvas) {
    const ctx = canvas.getContext('2d');
    
    // 노드 표시
    cy.nodes().forEach(node => {
        const pos = node.position();
        ctx.fillStyle = '#61dafb';
        ctx.fillRect(x, y, 2, 2);
    });
    
    // 뷰포트 박스
    ctx.strokeStyle = '#ff6b6b';
    ctx.strokeRect(...);
}
```

---

## 9. 내보내기 (Export)

**기능**: 그래프를 이미지 또는 데이터로 내보내기

### 지원 포맷
1. **PNG** - 전체 그래프 이미지 (2x scale)
2. **CSV** - 선택된 노드의 메트릭

### 사용법
```javascript
// PNG 내보내기
exportGraph('png');  // dkg_graph.png 다운로드

// CSV 내보내기
exportGraph('csv');  // dkg_nodes.csv 다운로드
```

### CSV 포맷
```csv
ID,Label,EntityClass,Slack,ArrivalTime,ClockDomain
"n_001","FF1","FlipFlop",-0.234,2.567,"clk"
"n_002","LUT1","LUT",0.456,1.234,"clk"
...
```

### 툴바 버튼
- 💾 PNG - PNG 이미지 내보내기
- 📊 CSV - CSV 데이터 내보내기

---

## 10. Critical Path 하이라이팅

**기능**: 최악의 타이밍 경로를 애니메이션으로 추적

### 동작 방식
1. 가장 worst slack 노드 찾기
2. 시작점 → 끝점 경로 계산
3. 순차적으로 노드/엣지 하이라이트
4. 빨간색 굵은 라인으로 표시

### 사용법
```javascript
// Critical Path 표시
showCriticalPath();  // 툴바 "🔴 Critical Path" 버튼

// 초기화
resetCriticalPath();  // 툴바 "⚪ Clear Path" 버튼
```

### API
```http
GET /api/critical/path

Response:
{
  "nodes": ["n_001", "n_002", "n_003"],
  "edges": ["e_001", "e_002"],
  "total_delay": 3.456,
  "total_slack": -0.234
}
```

### 애니메이션
```javascript
async function animateCriticalPath(nodeIds, edgeIds) {
    for (let i = 0; i < nodeIds.length; i++) {
        // 노드 하이라이트
        cy.getElementById(nodeIds[i]).addClass('critical-path');
        
        // 엣지 하이라이트
        if (i < edgeIds.length) {
            cy.getElementById(edgeIds[i]).addClass('critical-path');
        }
        
        // 0.3초 대기
        await new Promise(resolve => setTimeout(resolve, 300));
    }
}
```

### 스타일
```css
.critical-path {
    line-color: #ff6b6b;
    border-color: #ff6b6b;
    border-width: 4px;
    width: 4px;
    animation: pulse 1s ease-in-out infinite;
}
```

---

## 키보드 단축키

| 단축키 | 기능 |
|--------|------|
| 좌클릭 | 노드 정보 표시 |
| 더블클릭 | 홉 제한 설정 |
| 우클릭 | 컨텍스트 메뉴 |
| Wheel | 줌 인/아웃 |
| Drag | 팬 이동 |
| Esc | 패널/메뉴 닫기 |

---

## 백엔드 API 요약

### 새로 추가된 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/node/<id>/hop_limited` | GET | N-홉 제한 그래프 |
| `/api/node/<id>/internal` | GET | SuperNode 내부 그래프 |
| `/api/node/<id>/analysis` | GET | 노드 Analysis 데이터 |
| `/api/supernodes` | GET | SuperNode 목록 |
| `/api/query` | POST | 자연어 쿼리 실행 |
| `/api/node/<id>/provenance` | GET | Provenance 정보 |
| `/api/critical/path` | GET | Critical Path 찾기 |
| `/api/views` | GET | 사용 가능한 뷰 목록 |
| `/api/paths` | GET | 두 노드 간 경로 |

---

## 성능 최적화

### 대용량 그래프 처리
```javascript
// 노드 개수 제한
const limit = 100;  // 기본값

// 레이지 로딩
loadGraphInChunks(data, chunkSize=50);

// 가상화
cy.style().selector('node:hidden').style({'display': 'none'});
```

### 메모리 관리
```javascript
// 이전 그래프 제거
cy.elements().remove();

// 새 그래프 추가
cy.add(elements);

// 레이아웃 적용
cy.layout(layoutOptions).run();
```

---

## 문제 해결

### 1. 그래프가 표시되지 않음
```bash
# 백엔드 확인
curl http://localhost:5000/api/statistics

# 브라우저 콘솔 확인
F12 → Console
```

### 2. 터미널 쿼리 실패
```javascript
// CORS 설정 확인
from flask_cors import CORS
CORS(app)
```

### 3. 미니맵이 업데이트되지 않음
```javascript
// 주기적 업데이트 확인
setInterval(() => updateMinimap(canvas), 1000);
```

### 4. Critical Path를 찾을 수 없음
```python
# Slack 데이터 확인
critical_nodes = query_api.find_critical_nodes(slack_threshold=0.0)
print(f"Found {len(critical_nodes)} critical nodes")
```

---

## 확장 기능

### 플러그인 추가
```html
<!-- Cytoscape Navigator (Advanced Minimap) -->
<script src="https://unpkg.com/cytoscape-navigator/cytoscape-navigator.js"></script>

<!-- Compound Node -->
<script src="https://unpkg.com/cytoscape-compound-drag-and-drop/cytoscape-compound-drag-and-drop.js"></script>
```

### 커스텀 쿼리 추가
```python
# web_server.py
@app.route('/api/query', methods=['POST'])
def execute_query():
    query_text = request.get_json()['query']
    
    # 커스텀 쿼리 파싱
    if 'my custom query' in query_text.lower():
        # 처리 로직
        results = {...}
    
    return jsonify(results)
```

---

## 참고 자료

- [Cytoscape.js Documentation](https://js.cytoscape.org/)
- [Flask API Best Practices](https://flask.palletsprojects.com/en/2.3.x/)
- [DKG Query API Guide](QUERY_API_GUIDE.md)
- [Task 12 Design vs Simulation](TASK_12_DESIGN_VS_SIMULATION.md)

---

## 마무리

모든 10가지 기능이 구현되었습니다:

✅ 1. 홉 제한 (더블클릭)  
✅ 2. 내부 보기 (우클릭)  
✅ 3. 확장 노드 정보 (좌클릭 + Analysis)  
✅ 4. 슈퍼노드 필터  
✅ 5. 쿼리 터미널  
✅ 6. View & Context 전환  
✅ 7. Cross-Probing (Provenance)  
✅ 8. 미니맵  
✅ 9. 내보내기 (PNG/CSV)  
✅ 10. Critical Path 하이라이팅  

**웹 서버 실행:**
```bash
python web_server.py
```

브라우저에서 `http://localhost:5000` 접속하여 모든 기능을 사용하세요!
