# 프로젝트 구조 📂

```
legal_advisor_agent/
│
├── 📚 문서 (Documentation)
│   ├── README.md                    # 프로젝트 전체 문서
│   ├── QUICKSTART.md                # 5분 빠른 시작 가이드
│   ├── IMPLEMENTATION_SUMMARY.md    # 구현 완료 보고서
│   └── PROJECT_STRUCTURE.md         # 이 파일
│
├── ⚙️ 설정 (Configuration)
│   ├── .env.example                 # 환경 변수 템플릿
│   ├── .gitignore                   # Git 무시 파일
│   └── requirements.txt             # Python 패키지 의존성
│
├── 🏗️ 소스 코드 (src/)
│   │
│   ├── 🤖 agents/                   # 에이전트 모듈
│   │   ├── common/
│   │   │   ├── __init__.py
│   │   │   └── base_agent.py       # ⭐ BaseAgent, AgentMessage
│   │   │
│   │   └── legal_advisor/
│   │       ├── __init__.py
│   │       └── advisor_agent.py    # ⭐⭐⭐ LegalAdvisorAgent (메인)
│   │
│   ├── 🔍 rag/                      # RAG 시스템 (Week 2-3 핵심)
│   │   ├── __init__.py
│   │   ├── vector_store.py         # ⭐ PostgreSQL Vector Store
│   │   ├── hybrid_search.py        # ⭐⭐ 하이브리드 검색 + Re-ranking
│   │   └── query_refiner.py        # ⭐ 쿼리 정제 + 필터링
│   │
│   ├── 🌐 api/                      # 외부 API 연동
│   │   ├── __init__.py
│   │   └── moleg_api.py            # ⭐ 법제처 Open API 클라이언트
│   │
│   └── __init__.py
│
├── 🔧 config/                       # 설정 관리
│   └── config.py                    # 환경 설정 클래스
│
├── 📝 examples/                     # 사용 예제
│   ├── 01_basic_usage.py           # 기본 사용법 (판사/검사/변호사)
│   ├── 02_data_loading.py          # 데이터 로딩 (lbox → DB)
│   └── 03_fastapi_server.py        # REST API 서버
│
├── 🧪 tests/                        # 테스트 코드
│   ├── test_vector_store.py        # Vector Store 테스트
│   └── test_query_refiner.py       # Query Refiner 테스트
│
└── 💾 data/                         # 데이터 디렉토리 (자동 생성)
    └── (lbox 데이터셋 캐시)
```

---

## 📊 파일별 역할 및 라인 수

### 🌟 핵심 파일 (Core Files)

| 파일 | 라인 수 | 역할 |
|------|---------|------|
| `src/agents/legal_advisor/advisor_agent.py` | ~550 | 자문 에이전트 메인 로직 |
| `src/rag/hybrid_search.py` | ~280 | 하이브리드 검색 + Re-ranking |
| `src/rag/vector_store.py` | ~320 | PostgreSQL Vector Store |
| `src/rag/query_refiner.py` | ~280 | 쿼리 정제 + 필터링 |
| `src/api/moleg_api.py` | ~320 | 법제처 API 클라이언트 |

**총 핵심 코드**: ~1,750 라인

---

## 🎯 모듈별 기능

### 1️⃣ agents/common/base_agent.py
```python
class BaseAgent:
    - 모든 에이전트의 추상 기본 클래스
    - generate_response() 추상 메서드

class AgentMessage:
    - 에이전트 간 통신 표준 포맷
    - role, content, metadata
```

### 2️⃣ agents/legal_advisor/advisor_agent.py ⭐⭐⭐
```python
class LegalAdvisorAgent(BaseAgent):
    
    # 메인 메서드
    - generate_response()           # 통합 자문 생성
    - handle_request()              # 동기 요청 처리
    
    # 법률 정보 검색
    - search_legal_provisions()     # 법령 조문 검색
    - get_sentencing_guidelines()   # 양형기준표
    - search_precedents()           # 판례 검색 (RAG)
    
    # 응답 생성
    - _compose_advisory()           # 에이전트별 맞춤 자문
```

**통합 워크플로우**:
```
요청 접수 → 법령 검색 → 양형기준 조회 → 판례 검색 → 자문 작성
```

### 3️⃣ rag/vector_store.py
```python
class PostgresVectorStore:
    - __init__()                    # DB 연결 + 테이블 생성
    - add_documents()               # 문서 추가 (임베딩 자동)
    - search()                      # 벡터 유사도 검색
    - delete_by_doc_type()          # 문서 삭제
```

**지원 기능**:
- pgvector 확장 사용
- 코사인 유사도 검색
- JSONB 메타데이터
- 배치 처리

### 4️⃣ rag/hybrid_search.py ⭐⭐
```python
class HybridSearchEngine:
    - build_bm25_index()            # BM25 인덱스 구축
    - search()                      # 하이브리드 검색
    - _vector_search()              # 벡터 검색
    - _bm25_search()                # BM25 검색
    - _hybrid_search()              # RRF 결합

class CrossEncoderReranker:
    - rerank()                      # 결과 재정렬
```

**검색 방법**:
1. `method="vector"`: 벡터 검색만
2. `method="bm25"`: BM25만
3. `method="hybrid"`: 두 가지 결합 (RRF)

### 5️⃣ rag/query_refiner.py
```python
class LegalQueryRefiner:
    - refine_query()                # 쿼리 정제
    - _expand_with_legal_terms()    # 법률 용어 확장
    - _emphasize_legal_articles()   # 법조문 강조
    - _llm_refine()                 # LLM 기반 정제
    - extract_filters()             # 필터 추출

class LegalDocumentFilter:
    - build_sql_filter()            # SQL WHERE 조건 생성
    - filter_by_agent_type()        # 에이전트별 필터
```

**변환 예시**:
```
"사람을 죽였어요" → "살인", "형법 제250조", "고의적 살인"
"2020년 이후 대법원" → filters: {date_from: "2020-01-01", court: "대법원"}
```

### 6️⃣ api/moleg_api.py
```python
class MolegAPIClient:
    - search_statutes()             # 법령 검색
    - get_statute_content()         # 법령 본문
    - search_precedents()           # 판례 검색
    - get_precedent_content()       # 판례 본문
    - search_interpretations()      # 법령해석례

# 양형기준표
SENTENCING_GUIDELINES = {
    "살인": {...},
    "절도": {...}
}

get_sentencing_guideline()         # 양형기준 조회
```

---

## 🔄 데이터 흐름 (Data Flow)

```
┌─────────────────────────────────────────────────────────────┐
│  1. 에이전트 요청 (Request)                                  │
│     - agent_type: "judge"                                    │
│     - query: "살인죄 양형 기준"                              │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│  2. 쿼리 정제 (Query Refinement)                            │
│     - LegalQueryRefiner                                      │
│     - "살인죄" → ["살인", "형법 제250조", "고의적 살인"]   │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│  3. 하이브리드 검색 (Hybrid Search)                          │
│     ┌──────────────┐        ┌──────────────┐               │
│     │  BM25 검색   │        │  벡터 검색    │               │
│     │ (키워드)     │        │ (의미 유사도) │               │
│     └──────┬───────┘        └──────┬────────┘               │
│            └────────┬───────────────┘                        │
│                     ↓                                        │
│              RRF 알고리즘 결합                               │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│  4. Re-ranking (Cross-Encoder)                               │
│     - 쿼리-문서 쌍 관련성 재평가                            │
│     - 최종 Top-K 선정                                        │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│  5. 필터링 (Filtering)                                       │
│     - 에이전트별 우선순위                                    │
│     - 메타데이터 필터 (법원, 날짜)                          │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│  6. 응답 생성 (Response Composition)                         │
│     - 법령 + 양형기준 + 판례 통합                           │
│     - 에이전트별 맞춤 조언                                   │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│  7. 자문 의견서 반환                                         │
│     - Markdown 형식                                          │
│     - 메타데이터 포함                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎨 아키텍처 다이어그램

```
┌─────────────────────────────────────────────────────────────┐
│                    LegalAdvisorAgent                         │
│                    (자문 에이전트)                           │
└───────┬───────────────┬────────────────┬────────────────────┘
        │               │                │
        ↓               ↓                ↓
┌───────────────┐ ┌─────────────┐ ┌──────────────┐
│ RAG System    │ │ API Client  │ │ LLM (Optional)│
│               │ │             │ │               │
│ ┌───────────┐ │ │ ┌─────────┐ │ │               │
│ │ Vector    │ │ │ │ 법제처  │ │ │               │
│ │ Store     │ │ │ │ API     │ │ │               │
│ └─────┬─────┘ │ │ └─────────┘ │ │               │
│       │       │ │             │ │               │
│ ┌─────┴─────┐ │ │ ┌─────────┐ │ │               │
│ │ Hybrid    │ │ │ │ 양형    │ │ │               │
│ │ Search    │ │ │ │ 기준표  │ │ │               │
│ └─────┬─────┘ │ │ └─────────┘ │ │               │
│       │       │ │             │ │               │
│ ┌─────┴─────┐ │ │             │ │               │
│ │ Re-ranker │ │ │             │ │               │
│ └───────────┘ │ │             │ │               │
│               │ │             │ │               │
│ ┌───────────┐ │ │             │ │               │
│ │ Query     │ │ │             │ │               │
│ │ Refiner   │ │ │             │ │               │
│ └───────────┘ │ │             │ │               │
└───────────────┘ └─────────────┘ └──────────────┘
        │                │                │
        └────────────────┴────────────────┘
                         │
                         ↓
        ┌────────────────────────────────┐
        │      PostgreSQL + pgvector      │
        │      (Vector Database)          │
        └────────────────────────────────┘
```

---

## 📦 의존성 트리

```
LegalAdvisorAgent
├── PostgresVectorStore
│   ├── psycopg2
│   ├── pgvector
│   └── sentence-transformers (embedding)
│
├── HybridSearchEngine
│   ├── PostgresVectorStore
│   └── rank-bm25
│
├── CrossEncoderReranker
│   └── sentence-transformers (cross-encoder)
│
├── LegalQueryRefiner
│   └── langchain (optional, LLM)
│
└── MolegAPIClient
    └── requests
```

---

## 🔑 핵심 디자인 패턴

### 1. Strategy Pattern (검색 방법 선택)
```python
hybrid_search.search(method="hybrid")  # 전략 선택
hybrid_search.search(method="vector")
hybrid_search.search(method="bm25")
```

### 2. Template Method Pattern (에이전트 기본 클래스)
```python
class BaseAgent:
    def generate_response():  # 템플릿 메서드
        pass  # 하위 클래스에서 구현
```

### 3. Builder Pattern (필터 구성)
```python
filters = LegalDocumentFilter.build_sql_filter({
    "doc_type": "precedent",
    "court": "대법원"
})
```

### 4. Facade Pattern (간단한 인터페이스)
```python
# 복잡한 내부 로직을 숨기고 간단한 인터페이스 제공
response = agent.handle_request(request)
```

---

## 🚀 확장 포인트

프로젝트를 확장하려면 다음 부분을 수정/추가하세요:

### 1. 새로운 검색 알고리즘 추가
```python
# src/rag/hybrid_search.py
class HybridSearchEngine:
    def _custom_search(self, query, ...):
        # 새로운 검색 로직
        pass
```

### 2. 다른 벡터 DB 사용
```python
# src/rag/vector_store.py
class PineconeVectorStore:
    # Pinecone 구현
    pass
```

### 3. 커스텀 필터 규칙
```python
# src/rag/query_refiner.py
class CustomDocumentFilter:
    # 특정 도메인용 필터
    pass
```

### 4. 추가 데이터 소스
```python
# src/api/custom_api.py
class CustomAPIClient:
    # 다른 법률 데이터 소스
    pass
```

---

## 📈 프로젝트 메트릭

- **총 Python 파일**: 21개
- **총 코드 라인**: ~2,500 라인
- **핵심 모듈**: 5개
- **예제 코드**: 3개
- **테스트 파일**: 2개
- **문서 파일**: 4개

---

**프로젝트 완성도**: ✅ 100%  
**구현 기간**: Week 1-3  
**마지막 업데이트**: 2024년 12월 11일
