# Legal Advisor Agent 🏛️⚖️

**법률 자문 에이전트** - 판사/검사/변호사 에이전트에게 관련 법령, 판례, 양형기준을 제공하는 AI 시스템

---

## 📋 목차

1. [프로젝트 개요](#프로젝트-개요)
2. [주요 기능](#주요-기능)
3. [설치 방법](#설치-방법)
4. [사용 방법](#사용-방법)
5. [프로젝트 구조](#프로젝트-구조)
6. [Week별 구현 내용](#week별-구현-내용)
7. [API 문서](#api-문서)

---

## 🎯 프로젝트 개요

이 프로젝트는 법률 AI 시스템에서 **자문 에이전트** 역할을 수행합니다.

### 역할
- 판사/검사/변호사 에이전트의 요청을 받아 법률 정보 제공
- 관련 법령 조문 검색
- 양형기준표 정보 제공
- 유사 판례 검색 (RAG 시스템)
- 법적 근거 종합 제시

### 기술 스택
- **LLM**: OpenAI GPT / LangChain
- **Embedding**: jhgan/ko-sroberta-multitask
- **Vector DB**: PostgreSQL + pgvector
- **Search**: Hybrid Search (BM25 + Vector)
- **Re-ranking**: Cross-Encoder
- **API**: 법제처 Open API

---

## ✨ 주요 기능

### Week 1 완료 ✅
- [x] 데이터셋 구조 분석 (lbox/lbox_open)
- [x] DB 스키마 정의
- [x] 임베딩 모델 선정
- [x] 벡터 DB 구축 (PostgreSQL + pgvector)

### Week 2 완료 ✅
- [x] ~~청킹 로직 구현~~ (불필요 - reason 필드가 이미 완결된 단위)
- [x] **하이브리드 검색 구현** (BM25 + Vector)
- [x] **쿼리 정제** (법률 용어 확장)
- [x] **Re-ranking** (Cross-Encoder)

### Week 3 완료 ✅
- [x] **RAG 검색 함수 모듈화**
- [x] **필터링 로직 설계** (에이전트별 맞춤)
- [x] **자문 에이전트 기능 구현**
- [x] **에이전트 연동 인터페이스** (FastAPI)

---

## 🚀 설치 방법

### 1. 저장소 클론 및 패키지 설치

```bash
cd legal_advisor_agent
pip install -r requirements.txt
```

### 2. PostgreSQL + pgvector 설치

```bash
# Docker 사용 (권장)
docker run -d \
  --name legal-postgres \
  -e POSTGRES_PASSWORD=mysecretpassword \
  -e POSTGRES_DB=legal_db \
  -p 5432:5432 \
  pgvector/pgvector:pg16

# 또는 로컬 설치
# https://github.com/pgvector/pgvector 참고
```

### 3. 환경 변수 설정

`.env.example`을 `.env`로 복사하고 수정:

```bash
cp .env.example .env
```

`.env` 파일 내용:

```env
# OpenAI API Key
OPENAI_API_KEY=sk-...

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=legal_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=mysecretpassword

# 법제처 API (선택사항)
MOLEG_API_KEY=your_key_here

# Search Settings
HYBRID_SEARCH_ALPHA=0.5
TOP_K_RESULTS=10
RERANK_TOP_K=5
```

### 4. 데이터 로드

```bash
python examples/02_data_loading.py
```

---

## 💡 사용 방법

### 방법 1: Python 스크립트

```python
from src.agents.legal_advisor.advisor_agent import LegalAdvisorAgent, AdvisoryRequest

# 에이전트 초기화
agent = LegalAdvisorAgent()

# 자문 요청
request = AdvisoryRequest(
    agent_type="judge",
    case_id="2024고합1234",
    query="살인죄 양형 기준",
    case_type="형사",
    top_k=5
)

# 응답 받기
response = agent.handle_request(request)
print(response["advisory"])
```

### 방법 2: FastAPI 서버

```bash
# 서버 시작
python examples/03_fastapi_server.py

# 브라우저에서 API 문서 확인
# http://localhost:8000/docs
```

**API 요청 예시**:

```bash
curl -X POST "http://localhost:8000/api/advisory/search" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prosecutor",
    "case_id": "2024고합5678",
    "query": "절도죄 구형 기준",
    "case_type": "형사",
    "top_k": 3
  }'
```

---

## 📁 프로젝트 구조

```
legal_advisor_agent/
├── src/
│   ├── agents/
│   │   ├── common/
│   │   │   └── base_agent.py          # 기본 에이전트 클래스
│   │   └── legal_advisor/
│   │       └── advisor_agent.py       # 자문 에이전트 메인 로직
│   ├── rag/
│   │   ├── vector_store.py            # PostgreSQL Vector Store
│   │   ├── hybrid_search.py           # 하이브리드 검색 + Re-ranking
│   │   └── query_refiner.py           # 쿼리 정제 및 필터링
│   └── api/
│       └── moleg_api.py               # 법제처 API 클라이언트
├── examples/
│   ├── 01_basic_usage.py              # 기본 사용 예제
│   ├── 02_data_loading.py             # 데이터 로딩
│   └── 03_fastapi_server.py           # API 서버
├── tests/
│   └── (테스트 코드)
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🗓️ Week별 구현 내용

### Week 1: 데이터 수집 및 전처리 ✅

| 작업 | 상태 | 비고 |
|------|------|------|
| 데이터셋 구조 분석 | ✅ | lbox/lbox_open 분석 완료 |
| DB 스키마 정의 | ✅ | PostgreSQL + pgvector |
| 전처리 규칙 정의 | ✅ | reason 필드 그대로 사용 |
| 임베딩 모델 선정 | ✅ | ko-sroberta-multitask |
| 벡터 DB 구축 | ✅ | legal_documents 테이블 |

### Week 2: RAG 시스템 고도화 ✅

| 작업 | 상태 | 구현 파일 |
|------|------|-----------|
| ~~청킹 로직~~ | ⏭️ | (스킵 - 불필요) |
| 하이브리드 검색 | ✅ | `hybrid_search.py` |
| 쿼리 정제 | ✅ | `query_refiner.py` |
| Re-ranking | ✅ | `hybrid_search.py` |

**핵심 구현**:

1. **하이브리드 검색**
   - BM25 키워드 검색
   - 벡터 유사도 검색
   - RRF (Reciprocal Rank Fusion) 결합

2. **쿼리 정제**
   - 일상 용어 → 법률 용어 변환
   - 법조문 추출 및 강조
   - LLM 기반 멀티 쿼리 생성

3. **Re-ranking**
   - Cross-Encoder로 정확도 향상
   - 쿼리-문서 쌍 관련성 재평가

### Week 3: 자문 에이전트 구현 ✅

| 작업 | 상태 | 구현 파일 |
|------|------|-----------|
| RAG 모듈화 | ✅ | `advisor_agent.py` |
| 필터링 로직 | ✅ | `query_refiner.py` |
| 자문 에이전트 | ✅ | `advisor_agent.py` |
| API 인터페이스 | ✅ | `fastapi_server.py` |

**핵심 구현**:

1. **필터링 로직**
   - 에이전트 유형별 필터 (judge/prosecutor/lawyer)
   - 문서 타입 필터 (precedent/statute/interpretation)
   - 메타데이터 필터 (법원, 날짜, 사건 유형)

2. **자문 에이전트**
   - `search_legal_provisions()`: 법령 검색
   - `get_sentencing_guidelines()`: 양형기준 조회
   - `search_precedents()`: 판례 검색 (RAG)
   - `_compose_advisory()`: 맞춤형 자문 작성

3. **API 인터페이스**
   - FastAPI REST API
   - 표준화된 요청/응답 포맷
   - 에이전트 간 통신 프로토콜

---

## 📚 API 문서

### AdvisoryRequest

```python
@dataclass
class AdvisoryRequest:
    agent_type: str        # 'judge', 'prosecutor', 'lawyer'
    case_id: str           # 사건 번호
    query: str             # 검색 쿼리
    case_type: str = None  # '형사', '민사', '행정'
    filters: dict = None   # 추가 필터
    top_k: int = 5         # 반환할 판례 수
```

### 응답 형식

```json
{
  "status": "success",
  "advisory": "## 법률 자문 의견서\n\n...",
  "metadata": {
    "case_id": "2024고합1234",
    "requesting_agent": "judge",
    "num_precedents": 5,
    "has_sentencing_info": true
  }
}
```

---

## 🔧 주요 메서드

### LegalAdvisorAgent

```python
# 1. 법령 검색
provisions = agent.search_legal_provisions(crime_type="살인")

# 2. 양형기준 조회
sentencing = agent.get_sentencing_guidelines(crime_type="살인")

# 3. 판례 검색 (RAG)
precedents = agent.search_precedents(case_info, context)

# 4. 통합 자문
response = agent.handle_request(request)
```

---

## 🧪 테스트

```bash
# 기본 예제 실행
python examples/01_basic_usage.py

# 데이터 로딩
python examples/02_data_loading.py

# API 서버 테스트
python examples/03_fastapi_server.py
```

---

## 📊 성능 최적화

### 하이브리드 검색 가중치 조정

`.env` 파일에서 `HYBRID_SEARCH_ALPHA` 값 조정:

- `0.0`: BM25만 사용 (키워드 중심)
- `0.5`: 균형 (권장)
- `1.0`: 벡터 검색만 사용 (의미 중심)

### Re-ranking 활성화/비활성화

```python
# Re-ranking 비활성화 (속도 우선)
agent = LegalAdvisorAgent(use_reranking=False)

# Re-ranking 활성화 (정확도 우선)
agent = LegalAdvisorAgent(use_reranking=True)
```

---

## 🤝 에이전트 연동 예시

### 판사 에이전트에서 자문 요청

```python
# 판사 에이전트 코드
import requests

response = requests.post(
    "http://localhost:8000/api/advisory/search",
    json={
        "agent_type": "judge",
        "case_id": "2024고합1234",
        "query": "살인죄 양형 기준",
        "case_type": "형사"
    }
)

advisory = response.json()["advisory"]
print(advisory)
```

---

## 📝 TODO

- [ ] 더 많은 법률 데이터 추가 (법령, 해석례 등)
- [ ] LLM 기반 쿼리 정제 개선
- [ ] 양형기준표 데이터 확장
- [ ] 캐싱 시스템 추가 (Redis)
- [ ] 검색 성능 벤치마크

---

## 📄 라이센스

MIT License

---

## 👥 개발팀

- **자문 에이전트 팀** (2인)
- 역할: RAG 시스템 구축 및 법률 정보 제공

---

## 📞 문의

프로젝트 관련 문의사항은 이슈를 등록해주세요.
