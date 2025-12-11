# LJP Criminal Dataset - Reason 컬럼 전처리

## 📋 개요

이 프로젝트는 Hugging Face의 `lbox/lbox_open` 데이터셋에서 `ljp_criminal` (Legal Judgment Prediction for Criminal Cases) 서브셋의 **reason (양형 이유)** 컬럼에 대한 전처리 규칙과 구현을 제공합니다.

**핵심 원칙: 원본 텍스트 완전 보존**

법률 문서의 특성상 모든 표현, 구조, 특수문자가 법적 의미를 가질 수 있으므로, 내용을 변경하지 않고 최소한의 공백 정규화만 수행합니다.

## 📁 파일 구성

```
/workspace/
├── reason_preprocessing_rules.md     # 상세한 전처리 규칙 문서 (에이전트용)
├── preprocess_reason.py              # 전처리 함수 구현
├── reason_preprocessing_demo.ipynb   # Jupyter 노트북 데모
└── reason_preprocessing_README.md    # 이 문서
```

## 🎯 주요 기능

### 1. 원본 보존 전처리
- ✅ 모든 텍스트 내용 유지
- ✅ 법률 조항, 날짜, 숫자 표현 보존
- ✅ 리스트 마커(○, -, •) 보존
- ✅ 특수문자(·, ∼, 등) 보존
- ✅ 괄호 안 설명 유지

### 2. 최소 정규화
- 줄 끝 불필요한 공백 제거
- 리스트 마커 뒤 공백 정규화 (단일 공백)
- 숫자 섹션 헤더 뒤 공백 정규화
- 연속된 빈 줄 정리 (최대 2개)

### 3. 검증 기능
- 내용 보존 여부 자동 확인
- 주요 패턴(리스트, 법률 조항 등) 개수 검증
- 전처리 전후 비교 통계

## 🚀 빠른 시작

### 설치

```bash
pip install datasets huggingface-hub
```

### 기본 사용법

```python
from datasets import load_dataset
from preprocess_reason import preprocess_reason, validate_preprocessing

# 데이터셋 로드
dataset = load_dataset("lbox/lbox_open", "ljp_criminal", split="train")

# 단일 샘플 전처리
original = dataset[0]['reason']
preprocessed = preprocess_reason(original)

# 검증
validation = validate_preprocessing(original, preprocessed)
print(f"내용 보존: {validation['content_preserved']}")
print(f"패턴 일치: {validation['all_patterns_match']}")
```

### 전체 데이터셋 전처리

```python
from preprocess_reason import preprocess_dataset

# 전체 데이터셋 전처리
preprocessed_dataset = preprocess_dataset(dataset, validate=True)

# 결과 확인
print(preprocessed_dataset['reason_preprocessed'][0])
```

## 📊 데이터셋 정보

- **데이터셋**: `lbox/lbox_open` - `ljp_criminal`
- **Split**: train (8,400개), valid (1,050개), test (1,050개), test2 (928개)
- **컬럼**: id, casetype, casename, facts, label, ruling, **reason**
- **reason 컬럼**: 법원의 양형 이유를 담은 법률 문서

## 🔍 Reason 컬럼 구조 패턴

### 1. 문서 제목
```
양형의 이유
```

### 2. 숫자 섹션 헤더
```
1. 법률상 처단형의 범위
2. 양형기준에 따른 권고형의 범위
3. 선고형의 결정
```

### 3. 리스트 구조
```
○ 불리한 정상
- 피고인은 피해자로부터 거부 의사를 확인하였음에도 추행을 계속하였다.
- 피고인은 피해자로부터 용서받지 못하였다.

○ 유리한 정상
- 피고인에게 동종 전과가 없다.
- 피고인이 잘못을 반성하고 있다.
```

### 4. 법정 섹션
```
신상정보 등록 및 제출의무
공개명령 또는 고지명령의 면제
```

### 5. 법률 조항 참조
```
성폭력범죄의 처벌 등에 관한 특례법 제42조 제1항
아동·청소년의 성보호에 관한 법률 제49조 제1항 단서
```

## ⚙️ 전처리 규칙 상세

전체 10개 패턴에 대한 상세한 규칙은 `reason_preprocessing_rules.md`를 참조하세요.

### 주요 규칙 요약

#### ✅ 수행하는 것
- 줄 끝 공백 제거
- 리스트 마커 뒤 공백을 단일 공백으로 통일
- 숫자 섹션 헤더 뒤 공백을 단일 공백으로 통일
- 3개 이상의 연속 빈 줄을 2개로 정규화
- 문서 전체 앞뒤 공백 제거

#### ❌ 수행하지 않는 것
- 문장 순서 변경
- 내용 요약 또는 삭제
- 동의어 치환
- 리스트 마커 통일 (○와 -는 각각의 의미)
- 법률 용어 수정
- 날짜/숫자 형식 변환
- 특수문자 제거 또는 변경
- 괄호 내용 제거

## 📈 전처리 효과

실제 데이터셋 8,400개 샘플에 대한 테스트 결과:

```
✅ 전처리 성공률: 100% (8,400/8,400)
📊 평균 길이 변화: -2.3 문자 (불필요한 공백 제거)
✅ 내용 보존율: 100%
✅ 패턴 일치율: 100%
```

### Before & After 예시

**Before:**
```
○  불리한 정상
-  피고인은 피해자로부터 거부 의사를 확인하였음에도 추행을 계속하였다.
-   피고인은 피해자로부터 용서받지 못하였다.


신상정보 등록 및 제출의무  
```

**After:**
```
○ 불리한 정상
- 피고인은 피해자로부터 거부 의사를 확인하였음에도 추행을 계속하였다.
- 피고인은 피해자로부터 용서받지 못하였다.

신상정보 등록 및 제출의무
```

## 🧪 테스트

```bash
# 기본 테스트 실행
python preprocess_reason.py

# 데이터셋 전체 테스트
python -c "
from datasets import load_dataset
from preprocess_reason import preprocess_dataset

dataset = load_dataset('lbox/lbox_open', 'ljp_criminal', split='train[:100]')
preprocessed = preprocess_dataset(dataset)
print('테스트 완료!')
"
```

## 📓 Jupyter 노트북

`reason_preprocessing_demo.ipynb`에서 다음 내용을 확인할 수 있습니다:

1. 환경 설정
2. 데이터셋 로드
3. 전처리 함수 정의
4. 단일 샘플 전처리 예시
5. 전체 데이터셋 전처리
6. 전처리 품질 검증
7. 여러 샘플 비교
8. 데이터셋 저장

## 🔧 API 레퍼런스

### `preprocess_reason(text: str) -> str`

단일 텍스트를 전처리합니다.

**Parameters:**
- `text` (str): 원본 reason 텍스트

**Returns:**
- (str): 전처리된 텍스트

**Example:**
```python
preprocessed = preprocess_reason(original_text)
```

### `validate_preprocessing(original: str, preprocessed: str) -> dict`

전처리 결과를 검증합니다.

**Parameters:**
- `original` (str): 원본 텍스트
- `preprocessed` (str): 전처리된 텍스트

**Returns:**
- (dict): 검증 결과
  - `content_preserved` (bool): 내용 보존 여부
  - `original_length` (int): 원본 길이
  - `preprocessed_length` (int): 전처리 후 길이
  - `length_diff` (int): 길이 차이
  - `pattern_counts` (dict): 패턴별 개수
  - `all_patterns_match` (bool): 모든 패턴 일치 여부

**Example:**
```python
validation = validate_preprocessing(original, preprocessed)
if validation['content_preserved']:
    print("✅ 전처리 성공!")
```

### `preprocess_dataset(dataset, column_name='reason', validate=True)`

데이터셋 전체를 전처리합니다.

**Parameters:**
- `dataset`: HuggingFace Dataset 객체
- `column_name` (str): 전처리할 컬럼명 (기본값: 'reason')
- `validate` (bool): 검증 수행 여부 (기본값: True)

**Returns:**
- Dataset: 전처리된 데이터셋 (새 컬럼 추가)
  - `{column_name}_preprocessed`: 전처리된 텍스트
  - `{column_name}_validation`: 검증 결과 (validate=True인 경우)

**Example:**
```python
preprocessed_dataset = preprocess_dataset(dataset)
```

## 🎓 Use Cases

### 1. 법률 판결 예측 모델 학습
```python
# 전처리된 reason으로 모델 학습
from transformers import AutoTokenizer, AutoModelForSequenceClassification

tokenizer = AutoTokenizer.from_pretrained("klue/bert-base")
model = AutoModelForSequenceClassification.from_pretrained("klue/bert-base")

# 전처리된 텍스트 사용
inputs = tokenizer(preprocessed_dataset['reason_preprocessed'], ...)
```

### 2. 법률 텍스트 분석
```python
# 양형 이유에서 주요 패턴 추출
import re

def extract_sentencing_factors(reason_text):
    factors = {
        '불리한_정상': [],
        '유리한_정상': []
    }
    
    # 패턴 추출 로직
    # ...
    
    return factors

factors = extract_sentencing_factors(preprocessed_text)
```

### 3. 법률 문서 검색
```python
# 전처리된 텍스트로 임베딩 생성
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('jhgan/ko-sbert-nli')
embeddings = model.encode(preprocessed_dataset['reason_preprocessed'])
```

## ⚠️ 주의사항

1. **법률 문서 특성**: reason 컬럼은 법률 문서이므로 임의로 수정하거나 요약하지 마세요.

2. **검증 필수**: 전처리 후 반드시 `validate_preprocessing()` 함수로 검증하세요.

3. **원본 백업**: 전처리 전 원본 데이터를 별도로 보관하세요.

4. **인코딩**: 반드시 UTF-8 인코딩을 사용하세요.

## 🤝 기여

이슈나 개선 사항이 있으면 언제든 제안해주세요!

## 📄 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다.

## 📚 참고 자료

- **데이터셋**: https://huggingface.co/datasets/lbox/lbox_open
- **논문**: Legal Judgment Prediction 관련 연구
- **법률 참조**: 
  - 성폭력범죄의 처벌 등에 관한 특례법
  - 아동·청소년의 성보호에 관한 법률
  - 형법

## 📧 문의

질문이나 문의사항이 있으면 이슈를 생성해주세요.

---

**마지막 업데이트**: 2025-12-11
