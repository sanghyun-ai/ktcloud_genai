# LJP Criminal 데이터셋 RAG 설정 가이드

## 개요
이 가이드는 `ljp_criminal` 데이터셋을 전처리하여 Pinecone 벡터 DB에 저장하고, RAG를 통해 판례를 검색할 수 있도록 설정하는 방법을 설명합니다.

## 사전 준비

### 1. 필요한 패키지 설치

```bash
pip install datasets pinecone-client sentence-transformers tqdm
```

### 2. Pinecone API 키 설정

Pinecone 계정을 생성하고 API 키를 발급받은 후, 환경변수로 설정합니다:

```bash
export PINECONE_API_KEY="your-api-key-here"
```

또는 Python 코드에서:

```python
import os
os.environ["PINECONE_API_KEY"] = "your-api-key-here"
```

## 데이터 전처리 및 업로드

### 기본 사용법

```bash
python preprocess_ljp_criminal_for_rag.py --split train
```

### 옵션 설명

- `--split`: 처리할 데이터셋 split (`train`, `valid`, `test`, `test2`)
- `--max-cases`: 최대 처리할 사건 수 (테스트용, 기본값: 전체)
- `--batch-size`: 배치 크기 (기본값: 100)
- `--embedding-model`: 임베딩 모델 (기본값: `jhgan/ko-sroberta-multitask`)
- `--index-name`: Pinecone 인덱스 이름 (기본값: `ljp-criminal-rag`)
- `--test-search`: 업로드 후 검색 테스트 쿼리

### 예제

```bash
# 전체 train 데이터 업로드
python preprocess_ljp_criminal_for_rag.py --split train

# 테스트용으로 100건만 업로드
python preprocess_ljp_criminal_for_rag.py --split train --max-cases 100

# 업로드 후 검색 테스트
python preprocess_ljp_criminal_for_rag.py --split train --test-search "강제추행 징역"
```

## 전처리 전략

### 청크 분할 방식

각 판례는 다음과 같이 4가지 청크로 분할됩니다:

1. **전체 판례 (full_case)**: 사건명, 사실, 판결, 이유를 모두 포함
   - 우선순위: 높음
   - 용도: 전체적인 판례 검색

2. **사실 관계 (facts)**: 사건 사실만 포함
   - 우선순위: 중간
   - 용도: 유사한 사건 상황 검색

3. **판결 이유 (reason)**: 판결 이유만 포함
   - 우선순위: 중간
   - 용도: 법리 및 판단 근거 검색

4. **판결 내용 (ruling)**: 판결 내용 및 형량 정보 포함
   - 우선순위: 중간
   - 용도: 형량 및 판결 결과 검색

### 메타데이터 구조

각 청크는 다음 메타데이터를 포함합니다:

```python
{
    'chunk_type': 'full_case' | 'facts' | 'reason' | 'ruling',
    'case_id': int,  # 원본 사건 ID
    'casename': str,  # 사건명 (예: "강제추행")
    'casetype': str,  # 사건 유형 (예: "criminal")
    'priority': 'high' | 'medium',  # 검색 우선순위
    'imprisonment_lv': int,  # 징역 수준 (ruling 청크에만)
    'fine_lv': int  # 벌금 수준 (ruling 청크에만)
}
```

## RAG 검색 사용법

### 기본 검색

```python
from rag_search_utility import LJPRAGSearch

# 초기화
rag_search = LJPRAGSearch()

# 검색
results = rag_search.search("강제추행 징역 6개월", top_k=5)

# 결과 출력
for result in results:
    print(f"사건명: {result.casename}")
    print(f"유사도: {result.score:.4f}")
    print(f"내용: {result.text[:200]}...")
    print()
```

### 특정 사건 유형으로 필터링

```python
# 강제추행 사건만 검색
results = rag_search.search_by_case_type(
    query="징역 형량",
    casename="강제추행",
    top_k=5
)
```

### 우선순위 높은 판례만 검색

```python
# 전체 판례만 검색 (full_case 청크)
results = rag_search.search_high_priority(
    query="강제추행 처벌",
    top_k=5
)
```

### 메타데이터 필터링

```python
# 특정 조건으로 필터링
results = rag_search.search(
    query="징역",
    top_k=5,
    filter_dict={
        'casename': '강제추행',
        'priority': 'high'
    }
)
```

## 에이전트에서 활용 예시

### 변호사 에이전트 예시

```python
from rag_search_utility import LJPRAGSearch

class DefenseAttorneyAgent:
    def __init__(self):
        self.rag_search = LJPRAGSearch()
    
    def find_similar_cases(self, case_facts: str):
        """유사한 판례 검색"""
        # 사건 사실을 기반으로 유사 판례 검색
        results = self.rag_search.search(
            query=case_facts,
            top_k=5,
            filter_dict={'priority': 'high'}
        )
        
        # 유리한 판례만 선별 (형량이 낮거나 무죄 판결)
        favorable_cases = [
            r for r in results 
            if r.metadata.get('imprisonment_lv', 10) <= 2
        ]
        
        return favorable_cases
    
    def build_defense_argument(self, case_facts: str):
        """변호 논거 구성"""
        # 유사 판례 검색
        similar_cases = self.find_similar_cases(case_facts)
        
        # 판결 이유에서 유리한 법리 추출
        reasoning_results = self.rag_search.search(
            query=case_facts,
            top_k=3,
            filter_dict={'chunk_type': 'reason'}
        )
        
        # 논거 구성
        argument = f"""
        유사 판례 분석:
        {self.rag_search.format_search_results(similar_cases[:3])}
        
        참고 법리:
        {self.rag_search.format_search_results(reasoning_results)}
        """
        
        return argument
```

### 검사 에이전트 예시

```python
class ProsecutorAgent:
    def __init__(self):
        self.rag_search = LJPRAGSearch()
    
    def find_precedents(self, case_facts: str, casename: str):
        """유사 사건의 판례 검색"""
        results = self.rag_search.search_by_case_type(
            query=case_facts,
            casename=casename,
            top_k=5
        )
        return results
    
    def build_prosecution_argument(self, case_facts: str, casename: str):
        """기소 논거 구성"""
        # 동일 사건 유형의 판례 검색
        precedents = self.find_precedents(case_facts, casename)
        
        # 판결 내용에서 형량 정보 추출
        ruling_results = self.rag_search.search(
            query=f"{casename} 형량",
            top_k=5,
            filter_dict={'chunk_type': 'ruling'}
        )
        
        argument = f"""
        유사 사건 판례:
        {self.rag_search.format_search_results(precedents)}
        
        참고 형량:
        {self.rag_search.format_search_results(ruling_results)}
        """
        
        return argument
```

### 판사 에이전트 예시

```python
class JudgeAgent:
    def __init__(self):
        self.rag_search = LJPRAGSearch()
    
    def research_precedents(self, case_facts: str, casename: str):
        """판결을 위한 판례 연구"""
        # 전체 판례 검색
        full_cases = self.rag_search.search_high_priority(
            query=case_facts,
            top_k=10
        )
        
        # 판결 이유 검색
        reasons = self.rag_search.search(
            query=case_facts,
            top_k=5,
            filter_dict={'chunk_type': 'reason'}
        )
        
        return {
            'full_cases': full_cases,
            'reasons': reasons
        }
    
    def make_judgment(self, case_facts: str, casename: str):
        """판결 작성"""
        research = self.research_precedents(case_facts, casename)
        
        # 가장 유사한 판례 참고
        most_similar = research['full_cases'][0]
        
        judgment = f"""
        판결 근거:
        {self.rag_search.format_search_results(research['reasons'][:3])}
        
        참고 판례:
        {most_similar.text}
        """
        
        return judgment
```

## 임베딩 모델 선택

### 추천 모델

1. **jhgan/ko-sroberta-multitask** (기본값)
   - 한국어 특화
   - 법률 도메인에 적합
   - 768차원

2. **sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2**
   - 다국어 지원
   - 빠른 속도
   - 384차원

3. **BM-K/KoSimCSE-roberta-multitask**
   - 한국어 문장 유사도에 특화
   - 768차원

### 모델 변경 방법

```python
preprocessor = LJPPreprocessor(
    embedding_model_name="BM-K/KoSimCSE-roberta-multitask",
    dimension=768  # 모델에 맞게 차원 수 조정
)
```

## 주의사항

1. **비용 관리**: Pinecone은 사용량에 따라 비용이 발생합니다. 테스트 시 `--max-cases` 옵션을 사용하세요.

2. **인덱스 이름**: 여러 환경에서 사용할 경우 인덱스 이름을 다르게 설정하세요.

3. **텍스트 저장**: 현재 구현은 메타데이터에 텍스트를 포함하지만, 텍스트가 길 경우 별도 저장소를 사용하는 것을 권장합니다.

4. **청크 크기**: 필요에 따라 청크 분할 전략을 수정할 수 있습니다. `create_chunks` 메서드를 커스터마이징하세요.

## 문제 해결

### Pinecone 인덱스가 이미 존재하는 경우
스크립트가 자동으로 기존 인덱스를 사용합니다. 새로 시작하려면 Pinecone 대시보드에서 인덱스를 삭제하거나 다른 이름을 사용하세요.

### 메모리 부족
`--batch-size`를 줄이거나 `--max-cases`로 데이터 양을 제한하세요.

### 검색 결과가 부정확한 경우
- 더 적합한 임베딩 모델 사용
- 쿼리 프롬프트 개선
- 필터 조건 조정
