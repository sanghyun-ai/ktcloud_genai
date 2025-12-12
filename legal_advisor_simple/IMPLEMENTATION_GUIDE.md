# 구현 가이드 📝

**법률 자문 에이전트 - TODO 구현 방법**

---

## 🎯 구현해야 할 3가지 메서드

당신이 구현해야 할 메서드는 다음 3가지입니다:

```python
# src/agents/legal_advisor/advisor_agent.py

1. search_legal_provisions(crime_type: str)     # 법령 검색
2. get_sentencing_guidelines(crime_type: str)   # 양형기준 조회
3. search_precedents(case_info: Dict)           # 판례 검색
```

---

## 📚 1. search_legal_provisions() 구현

### 목표
범죄 유형을 입력받아 관련 법령 조문을 검색

### 구현 방법

#### Option 1: 법제처 API 사용 (권장)

```python
from src.api.moleg_api import MolegAPIClient

def search_legal_provisions(self, crime_type: str) -> List[Dict[str, Any]]:
    """관련 법령 조문 검색"""
    
    # 1. API 클라이언트 초기화
    api_client = MolegAPIClient()
    
    # 2. 법령 검색
    statutes = api_client.search_statutes(query=crime_type, display=5)
    
    if not statutes:
        return []
    
    # 3. LawItem 형식으로 변환
    laws = []
    for statute in statutes:
        # 상세 정보 조회
        detail = api_client.get_statute_content(statute["id"])
        
        if detail:
            laws.append({
                "law_name": detail["name"],
                "article_number": "전체",  # TODO: 조문 파싱 필요
                "content": detail["content"][:500],  # 일부만
                "relevant_reason": f"{crime_type}와 관련된 법령"
            })
    
    return laws
```

#### Option 2: 하드코딩된 매핑 사용 (빠른 테스트용)

```python
LAW_MAPPING = {
    "살인": {
        "law_name": "형법",
        "article_number": "제250조",
        "article_title": "살인",
        "content": "사람을 살해한 자는 사형, 무기 또는 5년 이상의 징역에 처한다."
    },
    "절도": {
        "law_name": "형법",
        "article_number": "제329조",
        "article_title": "절도",
        "content": "타인의 재물을 절취한 자는 6년 이하의 징역 또는 1천만원 이하의 벌금에 처한다."
    }
}

def search_legal_provisions(self, crime_type: str) -> List[Dict[str, Any]]:
    """관련 법령 조문 검색 (하드코딩)"""
    
    if crime_type in LAW_MAPPING:
        law = LAW_MAPPING[crime_type]
        law["relevant_reason"] = f"{crime_type}의 기본 법조문"
        return [law]
    
    return []
```

---

## ⚖️ 2. get_sentencing_guidelines() 구현

### 목표
범죄 유형의 양형기준표 정보 제공

### 구현 방법

#### Option 1: 샘플 데이터 사용 (빠른 시작)

```python
from src.api.moleg_api import get_sentencing_guideline

def get_sentencing_guidelines(self, crime_type: str) -> Optional[Dict[str, Any]]:
    """양형기준표 정보 제공"""
    
    # 샘플 데이터에서 조회
    guideline = get_sentencing_guideline(crime_type)
    
    if not guideline:
        return None
    
    # SentencingGuidelines 형식으로 변환
    basic_range = guideline["기준"]["일반적 기준"]["기본"]
    # "7년 ~ 11년" → 84~132개월
    
    return {
        "crime_type": crime_type,
        "legal_basis": guideline["법조문"],
        "basic_range": {
            "min_months": 84,  # TODO: 문자열 파싱 필요
            "max_months": 132,
            "description": basic_range
        },
        "mitigating_factors": guideline["기준"].get("감경요소", []),
        "aggravating_factors": guideline["기준"].get("가중요소", [])
    }
```

#### Option 2: CSV/JSON 파일 사용

```python
import json

def get_sentencing_guidelines(self, crime_type: str) -> Optional[Dict[str, Any]]:
    """양형기준표 정보 제공 (파일 기반)"""
    
    # data/sentencing_guidelines.json 로드
    with open("data/sentencing_guidelines.json", "r") as f:
        guidelines_db = json.load(f)
    
    if crime_type in guidelines_db:
        return guidelines_db[crime_type]
    
    return None
```

---

## 🔎 3. search_precedents() 구현

### 목표
사건 정보를 입력받아 유사 판례 검색

### 구현 방법

#### Phase 1: 기본 키워드 검색

```python
def search_precedents(self, case_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """유사 판례 검색 (기본 버전)"""
    
    # 1. lbox 데이터셋 로드
    from datasets import load_dataset
    
    dataset = load_dataset("lbox/lbox_open", "ljp_criminal", split="train")
    
    # 2. 범죄 유형으로 필터링
    crime_type = case_info.get("crime_type", "")
    
    filtered = [
        sample for sample in dataset
        if crime_type in sample.get("casename", "")
    ][:5]  # 최대 5개
    
    # 3. PrecedentItem 형식으로 변환
    precedents = []
    for sample in filtered:
        precedents.append({
            "case_number": sample.get("id", "N/A"),
            "court": "지방법원",  # TODO: 메타데이터에서 추출
            "decision_date": "2020-01-01",  # TODO: 실제 날짜
            "summary": sample.get("reason", "")[:200],
            "relevance_score": 0.5  # TODO: 실제 유사도
        })
    
    return precedents
```

#### Phase 2: 벡터 검색 (고급)

```python
def search_precedents(self, case_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """유사 판례 검색 (벡터 검색)"""
    
    # 1. 임베딩 모델 로드
    from sentence_transformers import SentenceTransformer
    
    model = SentenceTransformer("jhgan/ko-sroberta-multitask")
    
    # 2. 쿼리 임베딩
    query = case_info.get("facts_summary", "")
    query_embedding = model.encode(query)
    
    # 3. 벡터 DB 검색 (PostgreSQL + pgvector)
    # TODO: 벡터 DB 연동
    
    # 4. 결과 반환
    return []
```

---

## 🔄 구현 순서 (권장)

### Step 1: 샘플 데이터로 빠른 테스트 ⏱️ 30분

```python
# 1. search_legal_provisions() - 하드코딩
LAW_MAPPING = {...}

# 2. get_sentencing_guidelines() - 샘플 데이터
from src.api.moleg_api import get_sentencing_guideline

# 3. search_precedents() - 빈 리스트 반환 (일단 스킵)
return []
```

**목표**: 법령 + 양형기준만 먼저 작동시키기

---

### Step 2: 법제처 API 연동 ⏱️ 1-2시간

```python
# moleg_api.py 구현
class MolegAPIClient:
    def search_statutes(self, query):
        # API 호출 로직
        pass
```

**목표**: 실제 법령 데이터 가져오기

---

### Step 3: 판례 검색 (키워드 기반) ⏱️ 2-3시간

```python
# lbox 데이터셋으로 키워드 검색
from datasets import load_dataset

dataset = load_dataset("lbox/lbox_open", ...)
```

**목표**: 간단한 판례 검색 기능

---

### Step 4: 벡터 검색 (선택) ⏱️ 1일+

```python
# PostgreSQL + pgvector 설정
# 임베딩 모델 사용
# 유사도 검색
```

**목표**: 고급 RAG 기능

---

## 📝 구현 예시 (전체)

### advisor_agent.py (구현 완료 버전)

```python
from src.api.moleg_api import MolegAPIClient, get_sentencing_guideline
from datasets import load_dataset

class LegalAdvisorAgent(BaseAgent):
    
    def __init__(self):
        super().__init__(name="LegalAdvisorAgent", role="legal_advisor")
        self.api_client = MolegAPIClient()
        
        # lbox 데이터셋 로드 (초기화 시 한 번만)
        print("📚 판례 데이터셋 로딩...")
        self.precedents_dataset = load_dataset(
            "lbox/lbox_open",
            "ljp_criminal",
            split="train"
        )
    
    def search_legal_provisions(self, crime_type: str):
        """법령 검색 - 법제처 API"""
        statutes = self.api_client.search_statutes(
            query=crime_type,
            display=3
        )
        
        laws = []
        for statute in statutes:
            laws.append({
                "law_name": statute["name"],
                "article_number": "전체",
                "content": statute.get("summary", "")[:500]
            })
        
        return laws
    
    def get_sentencing_guidelines(self, crime_type: str):
        """양형기준 - 샘플 데이터"""
        return get_sentencing_guideline(crime_type)
    
    def search_precedents(self, case_info: Dict[str, Any]):
        """판례 검색 - 키워드 기반"""
        crime_type = case_info.get("crime_type", "")
        
        # 범죄 유형으로 필터링
        matches = [
            sample for sample in self.precedents_dataset
            if crime_type in sample.get("casename", "")
        ][:5]
        
        precedents = []
        for sample in matches:
            precedents.append({
                "case_number": sample["id"],
                "court": "지방법원",
                "decision_date": "2020-01-01",
                "summary": sample["reason"][:200],
                "relevance_score": 0.7
            })
        
        return precedents
```

---

## 🧪 테스트 방법

```bash
# 1. 예제 실행
python examples/basic_usage.py

# 2. 결과 확인
# - retrieval.status가 "success"로 바뀌었는지
# - outputs.laws에 법령이 있는지
# - outputs.sentencing_guidelines가 null이 아닌지
# - outputs.precedents에 판례가 있는지
```

---

## 📊 성공 기준

### ✅ 최소 구현 (MVP)
- [ ] `search_legal_provisions()` 구현
- [ ] `get_sentencing_guidelines()` 구현
- [ ] 스키마 형식에 맞는 데이터 반환
- [ ] `retrieval.status`가 "success" 표시

### ✅ 권장 구현
- [ ] 법제처 API 연동
- [ ] 양형기준표 DB 구축
- [ ] 판례 키워드 검색

### ✅ 고급 구현 (선택)
- [ ] 벡터 검색 (PostgreSQL + pgvector)
- [ ] 하이브리드 검색
- [ ] Re-ranking

---

## 💡 팁

1. **단계적 구현**: 한 번에 다 하려고 하지 말고, Step 1 → Step 2 → Step 3 순서로
2. **테스트 주도**: 각 단계마다 `basic_usage.py`로 테스트
3. **로깅 추가**: `print()`로 중간 과정 확인
4. **에러 처리**: try-except로 API 실패 대응

---

**구현 시작하세요!** 🚀

궁금한 점이 있으면 질문하세요.
