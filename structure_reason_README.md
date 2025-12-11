# LJP Criminal Dataset - Reason 컬럼 구조화

## 📋 개요

`lbox/lbox_open` 데이터셋의 `ljp_criminal` (Legal Judgment Prediction for Criminal Cases) 서브셋에서 **reason (양형 이유)** 컬럼을 구조화된 JSON 형식으로 변환하는 프로젝트입니다.

법률 판결문의 양형 이유 텍스트를 분석하여 불리한/유리한 정상, 양형기준, 신상정보 등의 정보를 자동으로 추출하고 구조화합니다.

## 🎯 주요 기능

### 1. 패턴 타입 자동 감지 (5가지)

- ✅ **기본 서술형** (Basic Narrative): 자유 서술 형식
- ✅ **구조화된 양형기준형** (Structured Guideline): 3단계 구조 (법률상 처단형, 양형기준, 선고형)
- ✅ **약식 생략형** (Omitted): "생략" 표시만 존재
- ✅ **신상정보 포함형** (With Personal Info): 신상정보 및 공개명령 관련 내용 포함
- ✅ **혼합형** (Hybrid): 부분적 구조화 + 서술형

### 2. 양형 이유 추출

- **불리한 정상** (unfavorable_factors): 피고인에게 불리한 양형 요소
- **유리한 정상** (favorable_factors): 피고인에게 유리한 양형 요소
- **법률상 처단형의 범위** (statutory_punishment_range)
- **양형기준** (sentencing_guidelines): 범죄 유형, 특별양형인자, 권고형 범위
- **선고형의 결정** (final_decision): 최종 형량 결정 이유
- **종합 고려사항** (general_considerations): 형법 제51조 양형조건 등

### 3. 신상정보 추출

- **등록의무** (registration_required): 신상정보 등록 대상 여부
- **공개명령 면제** (disclosure_exempted): 공개명령 면제 여부 및 이유
- **고지명령 면제** (notification_exempted)
- **취업제한** (employment_restriction)

## 📁 파일 구성

```
/workspace/
├── structure_reason.py                    # 핵심 구조화 함수
├── structure_reason_demo.ipynb            # Jupyter 노트북 데모
├── run_structure_reason.py                # 전체 데이터셋 구조화 스크립트
├── structure_reason_README.md             # 이 문서
└── ljp_criminal_reason_structured_sample.jsonl  # 샘플 결과 (100개)
```

## 🚀 빠른 시작

### 설치

```bash
pip install datasets huggingface-hub tqdm
```

### 기본 사용법

```python
from datasets import load_dataset
from structure_reason import structure_reason

# 데이터셋 로드
dataset = load_dataset("lbox/lbox_open", "ljp_criminal", split="train")

# 단일 샘플 구조화
reason_text = dataset[0]['reason']
case_id = dataset[0]['id']

structured = structure_reason(reason_text, case_id)
print(structured)
```

### 전체 데이터셋 구조화

```python
from structure_reason import structure_dataset

# 전체 데이터셋 구조화
structured_dataset = structure_dataset(dataset)

# 결과 확인
print(structured_dataset[0]['reason_structured'])
```

### 커맨드라인에서 실행

```bash
# 100개 샘플 테스트
python3 run_structure_reason.py

# 전체 데이터셋 (8,400개)
# 코드에서 split="train[:100]"을 split="train"으로 수정
```

## 📊 출력 JSON 스키마

```json
{
  "case_id": 0,
  "pattern_type": "구조화된 양형기준형",
  "sentencing_reason": {
    "statutory_punishment_range": "징역 1월 ~ 10년",
    "sentencing_guidelines": {
      "crime_type": "성범죄 > 01. 일반적 기준 > 나. 강제추행죄",
      "sentencing_type": "일반강제추행",
      "special_factors": {
        "aggravating": [],
        "mitigating": ["처벌불원"]
      },
      "recommended_range": "감경영역, 징역 1월~1년"
    },
    "unfavorable_factors": [
      "피고인은 피해자로부터 거부 의사를 확인하였음에도 추행을 계속하였다."
    ],
    "favorable_factors": [
      "피고인에게 동종 전과가 없다."
    ],
    "final_decision": "추행의 정도가 가볍지 않은 점을 고려하여...",
    "general_considerations": "그 밖에 피고인의 나이, 성행, 환경..."
  },
  "personal_information": {
    "registration_required": true,
    "registration_description": "성폭력범죄의 처벌 등에 관한 특례법 제42조...",
    "disclosure_exempted": true,
    "disclosure_exemption_reason": "피고인에게 동종전과가 없는 점...",
    "notification_exempted": true,
    "employment_restriction": false,
    "employment_restriction_exempted": false
  }
}
```

## 📈 테스트 결과 (100개 샘플)

### 패턴 분포

| 패턴 타입 | 개수 | 비율 |
|----------|------|------|
| 신상정보 포함형 | 33 | 33.0% |
| 기본 서술형 | 29 | 29.0% |
| 구조화된 양형기준형 | 19 | 19.0% |
| 약식 생략형 | 11 | 11.0% |
| 혼합형 | 8 | 8.0% |

### 추출 통계

- **불리한 정상 추출**: 26개 (26.0%)
- **유리한 정상 추출**: 30개 (30.0%)
- **신상정보 등록 필요**: 46개 (46.0%)
- **공개명령 면제**: 30개 (30.0%)

## 🔍 패턴 설명

### Pattern 1: 기본 서술형

자유로운 서술 형식으로 양형 요소를 나열합니다.

**예시:**
```
양형의 이유
피고인이 동종 범죄로 처벌받은 전력이 있는 점은 불리한 정상이다.
다만, 피고인이 범행을 시인하고 반성하고 있는 점은 유리한 정상이다.
```

**Detection Rules:**
- `양형의 이유`로 시작
- `불리한 정상` 또는 `유리한 정상` 키워드 포함
- 번호 체계나 표 형식 없음

### Pattern 2: 구조화된 양형기준형

법률상 처단형, 양형기준, 선고형 3단계로 구조화되어 있습니다.

**예시:**
```
양형의 이유
1. 법률상 처단형의 범위: 징역 1월 ~ 10년
2. 양형기준에 따른 권고형의 범위
   [유형의 결정] 성범죄 > 강제추행죄
   [특별양형인자] 감경요소: 처벌불원
   [권고영역] 감경영역, 징역 1월~1년
3. 선고형의 결정: ...
```

**Detection Rules:**
- `법률상 처단형의 범위` 포함
- `양형기준에 따른 권고형의 범위` 포함
- `선고형의 결정` 포함

### Pattern 3: 약식 생략형

양형 이유가 생략된 경우입니다.

**예시:**
```
양형의 이유
생략
```

**Detection Rules:**
- `양형의 이유` + `생략`만 존재

### Pattern 4: 신상정보 포함형

양형 이유 + 신상정보 등록/공개명령 관련 내용이 포함됩니다.

**예시:**
```
양형의 이유
○ 불리한 정상
- 피고인은 피해자로부터 용서받지 못하였다.
○ 유리한 정상
- 피고인에게 동종 전과가 없다.

신상정보 등록 및 제출의무
판시 범죄사실에 대하여 유죄판결이 확정되는 경우...

공개명령 또는 고지명령의 면제
피고인에게 동종전과가 없는 점 등을 종합하면...
```

**Detection Rules:**
- `신상정보 등록` 또는 `신상정보 제출의무` 포함
- `공개명령`, `고지명령` 키워드 포함

### Pattern 5: 혼합형

부분적으로 번호 체계를 사용하지만 완전한 3단계 구조는 아닙니다.

## ⚙️ API 레퍼런스

### `detect_pattern_type(text: str) -> ReasonPatternType`

reason 텍스트의 패턴 타입을 감지합니다.

**Parameters:**
- `text` (str): reason 텍스트

**Returns:**
- `ReasonPatternType`: 감지된 패턴 타입 (Enum)

### `structure_reason(text: str, case_id: Optional[str]) -> Dict[str, Any]`

단일 reason 텍스트를 구조화합니다.

**Parameters:**
- `text` (str): reason 텍스트
- `case_id` (Optional[str]): 케이스 ID

**Returns:**
- `Dict[str, Any]`: 구조화된 딕셔너리

**Example:**
```python
structured = structure_reason(reason_text, case_id=123)
print(structured['pattern_type'])
print(structured['sentencing_reason']['favorable_factors'])
```

### `structure_dataset(dataset, id_column='id', reason_column='reason')`

HuggingFace Dataset 전체를 구조화합니다.

**Parameters:**
- `dataset`: HuggingFace Dataset 객체
- `id_column` (str): ID 컬럼명 (기본값: 'id')
- `reason_column` (str): reason 컬럼명 (기본값: 'reason')

**Returns:**
- Dataset: 새로운 컬럼이 추가된 Dataset
  - `reason_structured`: 구조화된 데이터
  - `reason_pattern_type`: 패턴 타입

## 💡 활용 사례

### 1. 법률 판결 예측 모델 학습

```python
# 양형 요소를 피처로 사용
for example in structured_dataset:
    features = {
        'unfavorable_count': len(example['reason_structured']['sentencing_reason'].get('unfavorable_factors', [])),
        'favorable_count': len(example['reason_structured']['sentencing_reason'].get('favorable_factors', [])),
        'has_registration': example['reason_structured']['personal_information']['registration_required']
    }
    # 모델 학습에 사용
```

### 2. 양형 패턴 분석

```python
# 불리한 정상 분석
unfavorable_all = []
for example in structured_dataset:
    factors = example['reason_structured']['sentencing_reason'].get('unfavorable_factors', [])
    unfavorable_all.extend(factors)

# 빈도 분석
from collections import Counter
common_factors = Counter(unfavorable_all).most_common(10)
```

### 3. 유사 판례 검색

```python
# 양형 요소 기반 유사도 계산
def get_similarity(case1, case2):
    # 불리한/유리한 정상의 교집합 비율 계산
    unfav1 = set(case1['sentencing_reason'].get('unfavorable_factors', []))
    unfav2 = set(case2['sentencing_reason'].get('unfavorable_factors', []))
    
    if not unfav1 or not unfav2:
        return 0
    
    intersection = len(unfav1 & unfav2)
    union = len(unfav1 | unfav2)
    
    return intersection / union
```

### 4. 통계 분석

```python
import pandas as pd

# 패턴별 평균 형량 분석
data = []
for example in structured_dataset:
    data.append({
        'pattern': example['reason_pattern_type'],
        'imprisonment_lv': example['label']['imprisonment_with_labor_lv'],
        'has_unfavorable': bool(example['reason_structured']['sentencing_reason'].get('unfavorable_factors'))
    })

df = pd.DataFrame(data)
print(df.groupby('pattern')['imprisonment_lv'].mean())
```

## 📓 Jupyter 노트북

`structure_reason_demo.ipynb`에서 다음 내용을 확인할 수 있습니다:

1. 데이터셋 로드 및 패턴 분포 분석
2. 단일 샘플 구조화 예시
3. 전체 데이터셋 구조화
4. 통계 분석 및 시각화
5. JSON 파일로 저장

## ⚠️ 주의사항

1. **패턴 감지 정확도**: 일부 복잡한 케이스는 잘못 분류될 수 있습니다.

2. **추출 완전성**: 모든 양형 요소를 100% 추출하지는 못할 수 있습니다.
   - ○ 또는 - 마커 없이 서술된 경우 추출이 어려울 수 있음
   - 복잡한 문장 구조는 파싱이 불완전할 수 있음

3. **신상정보 추출**: 괄호 안의 긴 설명은 일부만 추출됩니다.

4. **성능**: 전체 8,400개 샘플 구조화는 약 3-5분 소요됩니다.

## 🔧 커스터마이징

### 추출 규칙 수정

`structure_reason.py`의 각 추출 함수를 수정하여 규칙을 조정할 수 있습니다:

- `extract_factors()`: 불리한/유리한 정상 추출 규칙
- `extract_sentencing_guidelines()`: 양형기준 추출 규칙
- `extract_personal_information()`: 신상정보 추출 규칙

### 새로운 필드 추가

```python
def extract_custom_field(text: str) -> str:
    """커스텀 필드 추출"""
    pattern = r'your_pattern_here'
    match = re.search(pattern, text)
    if match:
        return match.group(1)
    return None

# structure_reason() 함수에 추가
def structure_reason(text: str, case_id: Optional[str] = None):
    # ... 기존 코드 ...
    sentencing["custom_field"] = extract_custom_field(text)
    # ...
```

## 📊 전체 데이터셋 예상 통계

전체 8,400개 샘플 기준 예상 통계 (100개 샘플 결과 기반):

- **패턴 분포**:
  - 신상정보 포함형: ~2,800개 (33%)
  - 기본 서술형: ~2,400개 (29%)
  - 구조화된 양형기준형: ~1,600개 (19%)
  - 약식 생략형: ~900개 (11%)
  - 혼합형: ~700개 (8%)

- **추출률**:
  - 불리한 정상: ~2,200개 (26%)
  - 유리한 정상: ~2,500개 (30%)
  - 신상정보 등록: ~3,900개 (46%)
  - 공개명령 면제: ~2,500개 (30%)

## 🤝 기여

이슈나 개선 사항이 있으면 언제든 제안해주세요!

## 📄 라이선스

MIT License

## 📚 참고 자료

- **데이터셋**: https://huggingface.co/datasets/lbox/lbox_open
- **관련 프로젝트**: 
  - `reason_preprocessing_rules.md`: Reason 전처리 규칙
  - `preprocess_reason.py`: Reason 전처리 함수

---

**마지막 업데이트**: 2025-12-11

**문의**: 이슈 생성을 통해 문의해주세요.
