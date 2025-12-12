# Legal Advisor Agent (Simple Version) 🏛️

**법률 자문 에이전트 기본 골격** - 하이브리드 검색, 리랭킹 등 고급 기능 제외

---

## 📋 개요

이 프로젝트는 **법률 자문 에이전트의 기본 구조**만 포함합니다.

### 포함된 내용 ✅
- ✅ 기본 에이전트 골격 (`BaseAgent`, `LegalAdvisorAgent`)
- ✅ Pydantic 출력 스키마 (`legal_advice_schema.py`)
- ✅ 법제처 API 클라이언트 골격 (`moleg_api.py`)
- ✅ 기본 사용 예제

### 제외된 내용 ❌ (TODO)
- ❌ 하이브리드 검색 (BM25 + Vector)
- ❌ Re-ranking (Cross-Encoder)
- ❌ 쿼리 정제 (Query Refinement)
- ❌ 벡터 DB 연동 (PostgreSQL + pgvector)
- ❌ 실제 법령/양형/판례 조회 로직

---

## 🚀 빠른 시작

### 1. 설치

```bash
cd /workspace/legal_advisor_simple
pip install -r requirements.txt
```

### 2. 실행

```bash
python examples/basic_usage.py
```

### 3. 출력 예시

```
============================================================
🔍 법률 자문 요청 접수 (기본 버전)
============================================================
   사건번호: 2024고합1234
   범죄유형: 살인
   공소사실: ['형법 제250조']
============================================================

📚 1단계: 관련 법령 조회... (TODO: 구현 필요)
   ⚠️  법령 조회 미구현 - 빈 결과 반환
⚖️  2단계: 양형기준 조회... (TODO: 구현 필요)
   ⚠️  양형기준 조회 미구현 - None 반환
🔎 3단계: 유사 판례 검색... (TODO: 구현 필요)
   ⚠️  판례 검색 미구현 - 빈 결과 반환
✅ 자문 응답 생성 완료 (기본 버전)

📄 자문 결과 (JSON):
{
  "case": {
    "case_id": "2024고합1234",
    "crime_type": "살인",
    "charges": ["형법 제250조"],
    "facts_summary": "피고인은 2024년 5월 1일..."
  },
  "retrieval": {
    "query": {
      "crime_type": "살인",
      "keywords": ["살인"],
      ...
    },
    "status": {
      "laws": "fail",
      "sentencing_guidelines": "fail",
      "precedents": "fail"
    },
    "errors": [
      "법령 조회 미구현",
      "양형기준 조회 미구현",
      "판례 검색 미구현"
    ]
  },
  "outputs": {
    "laws": [],
    "sentencing_guidelines": null,
    "precedents": []
  },
  "analysis": {
    "issue_spotting": [],
    "legal_opinion": {
      "summary": "[기본 버전 응답]\n\n현재 단계에서는 살인 관련 법령/양형기준/판례 조회 기능이 미구현입니다...",
      "elements_checklist": [],
      "counterarguments": []
    }
  },
  "quality": {
    "confidence": 0.0,
    "coverage": {
      "laws": 0.0,
      "guidelines": 0.0,
      "precedents": 0.0
    },
    "notes": [
      "법령 조회 미구현 (MVP)",
      "양형기준 조회 미구현 (MVP)",
      "판례 검색 미구현 (MVP)"
    ],
    "manual_review_required": true
  }
}
```

---

## 📁 프로젝트 구조

```
legal_advisor_simple/
├── src/
│   ├── agents/
│   │   ├── common/
│   │   │   └── base_agent.py           # BaseAgent, AgentMessage
│   │   └── legal_advisor/
│   │       ├── advisor_agent.py        # LegalAdvisorAgent (메인)
│   │       └── legal_advice_schema.py  # Pydantic 스키마
│   └── api/
│       └── moleg_api.py                # 법제처 API 골격
│
├── examples/
│   └── basic_usage.py                  # 기본 사용 예제
│
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🎯 사용 방법

### Python 코드에서 사용

```python
import asyncio
from src.agents.legal_advisor.advisor_agent import LegalAdvisorAgent

# 에이전트 생성
agent = LegalAdvisorAgent()

# 사건 정보
case_info = {
    "case_id": "2024고합1234",
    "crime_type": "살인",
    "charges": ["형법 제250조"],
    "facts_summary": "피고인은..."
}

# 컨텍스트
context = {
    "requesting_agent": "judge"
}

# 자문 요청
response = asyncio.run(agent.generate_response(case_info, context))

# 결과 확인
print(response.content)  # JSON 문자열
print(response.metadata)  # 메타데이터
```

---

## 📊 출력 스키마

### LegalAdvisorOutput

```python
{
  "case": CaseInfo,              # 사건 정보
  "retrieval": RetrievalInfo,    # 검색 로그
  "outputs": LegalOutputs,       # 법률 자료
  "analysis": AnalysisResult,    # 분석 결과
  "citations": List[str],        # 인용 출처
  "quality": QualityInfo         # 품질 정보
}
```

### 주요 필드

- **CaseInfo**: 사건번호, 범죄유형, 공소사실, 사실관계 요약
- **RetrievalInfo**: 검색 쿼리, 상태(laws/sentencing/precedents), 에러
- **LegalOutputs**: 법령 리스트, 양형기준, 판례 리스트
- **AnalysisResult**: 쟁점 정리, 법률 의견
- **QualityInfo**: 신뢰도, 커버리지, 수동 검토 필요 여부

---

## 📝 TODO (구현 필요한 부분)

### 1. search_legal_provisions()
```python
def search_legal_provisions(self, crime_type: str):
    """
    TODO: 구현 필요
    - 법제처 API 호출
    - 범죄 유형에 따른 법령 매핑
    - 조문 내용 추출
    """
    pass
```

### 2. get_sentencing_guidelines()
```python
def get_sentencing_guidelines(self, crime_type: str):
    """
    TODO: 구현 필요
    - 양형기준표 DB 조회
    - 범죄 유형별 기준 형량 제공
    - 가중/감경 요소 제시
    """
    pass
```

### 3. search_precedents()
```python
def search_precedents(self, case_info: Dict[str, Any]):
    """
    TODO: 구현 필요
    - 벡터 DB 연동 (PostgreSQL + pgvector)
    - LBox Open 데이터 활용
    - 임베딩 모델로 유사도 검색
    """
    pass
```

---

## 🔧 구현 로드맵

### Phase 1: 기본 데이터 조회 ⏳
- [ ] 법제처 API 연동 (`moleg_api.py`)
- [ ] 양형기준표 데이터 구축
- [ ] 기본 법령 검색 구현

### Phase 2: 판례 검색 (RAG) ⏳
- [ ] 벡터 DB 설정 (PostgreSQL + pgvector)
- [ ] lbox 데이터 로딩
- [ ] 임베딩 모델 선정
- [ ] 기본 벡터 검색 구현

### Phase 3: 고급 기능 ⏳
- [ ] 하이브리드 검색 (BM25 + Vector)
- [ ] Re-ranking (Cross-Encoder)
- [ ] 쿼리 정제 (Query Refinement)

---

## 🎨 스키마 예시

### 완전한 응답 예시 (구현 후)

```json
{
  "case": {
    "case_id": "2024고합1234",
    "crime_type": "살인",
    "charges": ["형법 제250조"],
    "facts_summary": "피고인이 피해자를..."
  },
  "retrieval": {
    "status": {
      "laws": "success",
      "sentencing_guidelines": "success",
      "precedents": "success"
    }
  },
  "outputs": {
    "laws": [
      {
        "law_name": "형법",
        "article_number": "제250조",
        "article_title": "살인",
        "content": "사람을 살해한 자는 사형, 무기 또는 5년 이상의 징역에 처한다.",
        "relevant_reason": "본 사건의 기본 법조문"
      }
    ],
    "sentencing_guidelines": {
      "crime_type": "살인",
      "legal_basis": "형법 제250조",
      "basic_range": {
        "min_months": 84,
        "max_months": 132,
        "description": "7년~11년"
      },
      "mitigating_factors": ["우발적 범행", "진지한 반성"],
      "aggravating_factors": ["계획적 범행", "잔혹한 방법"]
    },
    "precedents": [
      {
        "case_number": "2020도12345",
        "court": "대법원",
        "decision_date": "2020-05-15",
        "summary": "피고인이 우발적으로...",
        "relevance_score": 0.92
      }
    ]
  },
  "analysis": {
    "issue_spotting": ["고의 인정 여부", "양형 감경 사유"],
    "legal_opinion": {
      "summary": "형법 제250조 살인죄가 성립하며, 기본 형량은 7년~11년입니다...",
      "elements_checklist": ["고의", "살해 행위", "사망 결과"]
    }
  },
  "quality": {
    "confidence": 0.85,
    "coverage": {
      "laws": 1.0,
      "guidelines": 1.0,
      "precedents": 0.8
    },
    "manual_review_required": false
  }
}
```

---

## 🤝 다른 에이전트와 통합

### 판사/검사/변호사 에이전트에서 호출

```python
# 판사 에이전트에서
from src.agents.legal_advisor.advisor_agent import LegalAdvisorAgent

legal_advisor = LegalAdvisorAgent()

response = await legal_advisor.generate_response(
    case_info={
        "case_id": "2024고합1234",
        "crime_type": "살인",
        ...
    },
    context={
        "requesting_agent": "judge"
    }
)

# JSON 파싱
import json
advice = json.loads(response.content)

# 법령 정보 활용
laws = advice["outputs"]["laws"]
sentencing = advice["outputs"]["sentencing_guidelines"]
```

---

## 📚 참고

- **법제처 Open API**: https://www.law.go.kr/DRF/lawService.do
- **LBox Open 데이터셋**: https://huggingface.co/datasets/lbox/lbox_open
- **Pydantic 문서**: https://docs.pydantic.dev/

---

## 📄 라이센스

MIT License

---

**현재 상태**: 기본 골격만 구현 (MVP)  
**다음 단계**: TODO 항목 구현 시작
