# DKG Web Viewer 사용 가이드

## 🚀 빠른 시작

### 1. 필수 패키지 설치

```bash
pip install flask flask-cors
```

### 2. 서버 실행

```bash
python web_server.py
```

서버가 시작되면 다음 주소에서 접속 가능합니다:
- **웹 UI**: http://localhost:5000
- **API 문서**: http://localhost:5000/api/statistics

### 3. 브라우저에서 열기

웹 브라우저에서 http://localhost:5000 을 열면 DKG Viewer가 표시됩니다.

## 📱 주요 기능

### 1️⃣ 검색
- **노드 이름 검색**: 사이드바 검색 탭에서 노드 이름 입력
- **실시간 자동완성**: 2글자 이상 입력하면 자동으로 검색
- **클릭하여 포커스**: 검색 결과 클릭 시 해당 노드로 이동

### 2️⃣ 필터링
- **Entity Class**: Flip-Flop, LUT, MUX 등으로 필터
- **Hierarchy**: 특정 모듈의 노드만 표시
- **Slack Range**: 타이밍 범위로 필터링
- **결과 제한**: 성능을 위해 표시할 노드 수 제한

### 3️⃣ 통계
- **전체 통계**: 노드/엣지 수, 최악의 슬랙
- **타이밍 위반**: 위반 개수 확인
- **Critical 노드**: 타이밍이 critical한 노드만 표시

### 4️⃣ 시각화
- **다양한 레이아웃**:
  - Breadthfirst: 계층적 트리 구조
  - COSE: 물리 기반 자동 배치
  - Circle: 원형 배치
  - Grid: 격자 배치
  - Dagre: 방향성 그래프 (가장 깔끔)

- **노드 스타일**:
  - 🔵 Flip-Flop: 파란색 사각형
  - 🟢 LUT: 초록색 삼각형
  - 🟠 MUX: 주황색 다이아몬드
  - 🟣 BRAM: 보라색 팔각형
  - 🔴 IO Port: 빨간색 육각형
  - ⚠️ Critical: 빨간색 테두리

### 5️⃣ 인터랙션
- **클릭**: 노드 선택 및 상세 정보 표시
- **마우스 오버**: 하이라이트 효과
- **이웃 강조**: 노드 클릭 시 연결된 노드/엣지 강조
- **줌/팬**: 마우스 휠 줌, 드래그로 이동

## 🎮 단축키 및 컨트롤

### 툴바 버튼
- **🔍 Fit**: 그래프 전체가 보이도록 조정
- **⊙ Center**: 그래프 중앙 정렬
- **↻ Reset**: 줌 및 위치 초기화

### 마우스 조작
- **왼쪽 클릭**: 노드/엣지 선택
- **휠**: 줌 인/아웃
- **드래그**: 그래프 이동
- **Shift + 드래그**: 다중 선택

## 🔌 API 엔드포인트

웹 서버는 RESTful API를 제공합니다:

### 통계 및 정보
```
GET /api/statistics              # 그래프 통계
GET /api/timing/summary           # 타이밍 요약
```

### 노드 쿼리
```
GET /api/nodes                    # 노드 목록
    ?entity_class=FlipFlop          (필터: 엔티티 클래스)
    ?hierarchy=cpu/alu              (필터: 계층)
    ?slack_min=-1&slack_max=0       (필터: 슬랙 범위)
    ?limit=100                      (결과 제한)

GET /api/node/<node_id>           # 노드 상세 정보
GET /api/search?q=<query>         # 노드 검색
```

### 엣지 쿼리
```
GET /api/edges                    # 엣지 목록
    ?src_node=<id>                  (소스 노드)
    ?dst_node=<id>                  (목적지 노드)
    ?relation_type=DataRelation     (관계 타입)
```

### 그래프
```
GET /api/graph                    # 전체 그래프
    ?hierarchy=cpu                  (서브그래프)
    ?entity_class=FlipFlop          (필터)
    ?limit=100                      (제한)

GET /api/neighborhood             # 노드 주변 그래프
    ?node_id=<id>&depth=1
```

### 경로 및 분석
```
GET /api/paths                    # 경로 탐색
    ?start=<id>&end=<id>&max_depth=10

GET /api/critical/nodes           # Critical 노드
    ?threshold=0.0&top_n=50

GET /api/critical/edges           # Critical 엣지
    ?threshold=1.0&top_n=20

GET /api/hierarchy                # 계층 구조
    ?parent=<path>
```

## 📝 사용 예시

### 예시 1: Critical 노드 찾기
1. 사이드바에서 **통계** 탭 선택
2. **Critical 노드 보기** 버튼 클릭
3. 타이밍이 critical한 상위 50개 노드 표시
4. 노드 클릭하여 상세 정보 확인

### 예시 2: 특정 모듈 탐색
1. **필터** 탭 선택
2. Hierarchy에 `cpu/alu` 입력
3. **필터 적용** 클릭
4. ALU 모듈의 노드들만 표시

### 예시 3: Flip-Flop만 보기
1. **필터** 탭에서 Entity Class를 `FlipFlop` 선택
2. Limit을 `200`으로 설정
3. **필터 적용**
4. 레이아웃을 `Dagre`로 변경하여 보기 좋게 정렬

### 예시 4: 노드 검색 및 이웃 확인
1. **검색** 탭에서 노드 이름 입력 (예: `pc_reg`)
2. 검색 결과에서 원하는 노드 클릭
3. 자동으로 해당 노드로 포커스 이동
4. 연결된 이웃 노드들이 하이라이트됨
5. 우측 정보 패널에서 팬인/팬아웃 확인

## ⚙️ 설정 및 커스터마이징

### 서버 설정
`web_server.py` 파일에서 설정 변경:

```python
# 디자인 경로 변경
config = YosysConfig(
    src_dir_win=r"C:\your\design\path",
    out_json_win=r"C:\your\output.json",
    top_module="your_top_module",
)

# 포트 변경
run_server(config, port=8080)
```

### 스타일 커스터마이징
`web/index.html`의 CSS 섹션에서 색상 및 스타일 변경 가능

### 노드 스타일 변경
`web/app.js`의 `initializeCytoscape()` 함수에서 Cytoscape 스타일 수정

## 🐛 문제 해결

### 그래프가 로드되지 않음
- 서버가 실행 중인지 확인: `python web_server.py`
- 브라우저 콘솔에서 에러 메시지 확인 (F12)
- API 엔드포인트 접속 테스트: http://localhost:5000/api/statistics

### 성능이 느림
- 필터 탭에서 **Limit** 값을 줄이기 (기본 100, 권장 50-200)
- 특정 모듈만 선택하여 표시 (Hierarchy 필터 사용)
- 레이아웃을 `Grid` 또는 `Circle`로 변경 (COSE는 느릴 수 있음)

### CORS 에러
- `flask-cors` 패키지가 설치되어 있는지 확인
- 브라우저 캐시 삭제 후 재시도

### 노드 정보가 표시되지 않음
- Query API가 제대로 초기화되었는지 확인
- 서버 콘솔에서 에러 로그 확인

## 📚 추가 리소스

- **Query API 가이드**: `QUERY_API_GUIDE.md`
- **DKG 설계 문서**: `DESIGN.md`
- **Cytoscape.js 문서**: https://js.cytoscape.org/

## 💡 팁

1. **큰 그래프**: Limit을 50-100으로 설정하고 필터 활용
2. **타이밍 분석**: Critical 노드 보기 → 상세 정보에서 팬인 확인
3. **모듈 탐색**: Hierarchy 필터로 관심 모듈만 집중 탐색
4. **경로 분석**: API를 직접 호출하여 경로 탐색
   ```javascript
   fetch('http://localhost:5000/api/paths?start=node1&end=node2')
   ```

## 🎨 스크린샷 가이드

### 메인 화면
- 왼쪽: 검색/필터/통계 사이드바
- 중앙: Cytoscape.js 그래프 시각화
- 우측: 선택한 노드/엣지 정보 패널

### 색상 범례
- 🔵 **Flip-Flop** (파란색 사각형)
- 🟢 **LUT** (초록색 삼각형)
- 🟠 **MUX** (주황색 다이아몬드)
- 🟣 **BRAM** (보라색 팔각형)
- 🔴 **IO Port** (빨간색 육각형)
- ⚠️ **빨간 테두리** = Critical (타이밍 위반)

---

**Enjoy exploring your design! 🚀**
