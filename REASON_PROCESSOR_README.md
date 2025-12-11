# Reason Processor - DB 통합 버전

## 📋 개요

`.env`의 `DATABASE_URL`에서 데이터를 불러와 reason 컬럼에 대해 **전처리 + 구조화**를 수행하고 JSON 파일로 저장하는 통합 스크립트입니다.

## ✨ 주요 특징

1. ✅ `.env`의 `DATABASE_URL`에서 데이터 로드
2. ✅ `reason` 값이 채워진 행만 처리
3. ✅ 하나의 파일에서 전처리 + 구조화 모두 수행
4. ✅ 별도 스크립트 파일 없음
5. ✅ 최종 결과를 JSON 파일로 저장

## 🚀 설치

```bash
# 필수 패키지 설치
pip install python-dotenv sqlalchemy psycopg2-binary tqdm

# MySQL 사용 시
pip install pymysql

# SQLite 사용 시 (추가 설치 불필요)
```

## ⚙️ 설정

### 1. .env 파일 생성

```bash
# .env.example을 .env로 복사
cp .env.example .env
```

### 2. DATABASE_URL 설정

`.env` 파일을 열고 데이터베이스 연결 정보를 입력:

**PostgreSQL:**
```
DATABASE_URL=postgresql://username:password@localhost:5432/database_name
```

**MySQL:**
```
DATABASE_URL=mysql+pymysql://username:password@localhost:3306/database_name
```

**SQLite:**
```
DATABASE_URL=sqlite:///./ljp_criminal.db
```

## 🎯 사용법

### 기본 실행

```bash
python reason_processor.py
```

### 출력 파일명 지정

```bash
python reason_processor.py --output custom_output.json
```

## 📊 처리 과정

1. **데이터 로드**: DATABASE_URL에서 reason이 NULL이 아니고 빈 문자열이 아닌 행만 로드
2. **전처리**: 각 행의 reason 텍스트를 전처리
   - 줄 끝 공백 제거
   - 리스트 마커 공백 정규화
   - 연속 빈 줄 정리
3. **구조화**: 전처리된 텍스트를 JSON으로 구조화
   - 패턴 타입 감지 (5가지)
   - 양형 요소 추출
   - 신상정보 추출
4. **저장**: 결과를 JSON 파일로 저장

## 📄 출력 JSON 형식

```json
[
  {
    "id": 0,
    "casetype": "criminal",
    "casename": "강제추행",
    "label": {...},
    "reason_original": "원본 텍스트...",
    "reason_preprocessed": "전처리된 텍스트...",
    "reason_structured": {
      "case_id": 0,
      "pattern_type": "신상정보 포함형",
      "sentencing_reason": {
        "unfavorable_factors": ["..."],
        "favorable_factors": ["..."],
        "general_considerations": "..."
      },
      "personal_information": {
        "registration_required": true,
        "disclosure_exempted": true
      }
    }
  }
]
```

## 🔍 SQL 쿼리

스크립트는 다음 쿼리를 사용합니다:

```sql
SELECT 
    id,
    casetype,
    casename,
    facts,
    label,
    ruling,
    reason
FROM ljp_criminal
WHERE reason IS NOT NULL 
  AND reason != ''
  AND TRIM(reason) != ''
```

**⚠️ 주의**: 테이블명(`ljp_criminal`)과 컬럼명은 실제 DB 구조에 맞게 수정해야 합니다.

## 🛠️ 테이블 구조 수정

실제 데이터베이스 테이블 구조가 다른 경우, `reason_processor.py` 파일의 `load_data_from_db()` 함수에서 쿼리를 수정하세요:

```python
def load_data_from_db():
    # ...
    query = """
    SELECT 
        your_id_column as id,
        your_casetype_column as casetype,
        your_reason_column as reason
    FROM your_table_name
    WHERE your_reason_column IS NOT NULL 
      AND your_reason_column != ''
    """
    # ...
```

## 📊 실행 예시

```bash
$ python reason_processor.py

================================================================================
LJP Criminal Dataset - Reason 전처리 및 구조화
================================================================================

1. 데이터베이스에서 데이터 로딩 중...
   ✓ reason 값이 있는 8400개 행 로드 완료

2. 전처리 및 구조화 진행 중...
   처리 중: 100%|██████████| 8400/8400 [00:45<00:00, 185.5it/s]
   ✓ 8400개 행 처리 완료

3. 처리 통계...
   패턴 타입 분포:
     - 신상정보 포함형: 2772개 (33.0%)
     - 기본 서술형: 2436개 (29.0%)
     - 구조화된 양형기준형: 1596개 (19.0%)
     - 약식 생략형: 924개 (11.0%)
     - 혼합형: 672개 (8.0%)

   추출 통계:
     - 불리한 정상: 2184개 (26.0%)
     - 유리한 정상: 2520개 (30.0%)

4. JSON 파일로 저장 중... (ljp_criminal_processed.json)
   ✓ 저장 완료: ljp_criminal_processed.json

================================================================================
✅ 모든 작업 완료!
✅ 결과 파일: ljp_criminal_processed.json
================================================================================
```

## ⚠️ 주의사항

### 1. DATABASE_URL 필수
`.env` 파일에 `DATABASE_URL`이 설정되지 않으면 에러가 발생합니다.

### 2. 테이블 구조
스크립트는 기본적으로 `ljp_criminal` 테이블을 가정합니다. 실제 테이블명이 다르면 코드를 수정해야 합니다.

### 3. 메모리 사용
모든 데이터를 메모리에 로드하므로, 데이터가 매우 큰 경우 배치 처리를 고려하세요.

### 4. NULL/빈 값 처리
- `reason IS NOT NULL`: NULL 값 제외
- `reason != ''`: 빈 문자열 제외
- `TRIM(reason) != ''`: 공백만 있는 경우 제외

## 🔧 커스터마이징

### 컬럼 추가

출력 JSON에 다른 컬럼을 추가하려면:

```python
result = {
    'id': row.get('id'),
    'casetype': row.get('casetype'),
    'casename': row.get('casename'),
    'label': row.get('label'),
    'your_custom_field': row.get('your_custom_field'),  # 추가
    'reason_original': original_reason,
    'reason_preprocessed': preprocessed_reason,
    'reason_structured': {...}
}
```

### 필터 조건 변경

특정 조건의 데이터만 처리하려면:

```python
query = """
SELECT * FROM ljp_criminal
WHERE reason IS NOT NULL 
  AND casetype = 'criminal'  -- 조건 추가
  AND label->>'imprisonment_with_labor_lv' > 0  -- JSON 필드 조건
"""
```

## 📚 함수 설명

### `preprocess_reason(text: str) -> str`
- 원본 텍스트 전처리
- 공백 정규화, 리스트 마커 정리
- 원본 내용 100% 보존

### `structure_reason(text: str, case_id) -> Dict`
- 전처리된 텍스트를 JSON으로 구조화
- 패턴 감지, 양형 요소 추출, 신상정보 추출

### `load_data_from_db() -> List[Dict]`
- DATABASE_URL에서 데이터 로드
- reason이 채워진 행만 반환

### `process_and_save(output_file: str)`
- 메인 처리 함수
- 로드 → 전처리 → 구조화 → 저장

## 🐛 트러블슈팅

### 1. "DATABASE_URL이 설정되지 않았습니다"
→ `.env` 파일을 생성하고 `DATABASE_URL`을 설정하세요.

### 2. "relation ljp_criminal does not exist"
→ 쿼리의 테이블명을 실제 테이블명으로 수정하세요.

### 3. 메모리 부족
→ 배치 처리를 구현하거나, 데이터를 분할하여 처리하세요.

### 4. "No module named 'psycopg2'"
→ `pip install psycopg2-binary` 실행

## 📞 문의

문제가 발생하면 이슈를 생성해주세요.

---

**마지막 업데이트**: 2025-12-11
